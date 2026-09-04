"""Vector store backed by SQLite with sqlite-vec or numpy-fallback cosine search.

The store is a simple table of document chunks paired with a vector table.
``sqlite-vec`` is preferred (C extension, ANN search) but the class falls
back to pure-Python numpy cosine if the extension cannot be loaded.

DB layout
---------
documents(id INTEGER PRIMARY KEY,
          source TEXT NOT NULL,
          domain TEXT NOT NULL,
          jurisdiction TEXT NOT NULL,
          citation TEXT NOT NULL,
          chunk_text TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(source, chunk_index))

vectors(id INTEGER PRIMARY KEY,
        chunk_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
        embedding BLOB NOT NULL)
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("osiris.vector_store")

EMBEDDING_DIM = 768


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _pack(vec: list[float]) -> bytes:
    return json.dumps(vec).encode("utf-8")


class VectorStore:
    """Thin wrapper around the SQLite-backed chunk + vector tables."""

    def __init__(self, db_path: str | Path = "data/rag.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._use_numpy = False
        self._numpy_vectors: dict[int, list[float]] = {}
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # sqlite-vec must be loaded on every connection — extensions are
        # per-connection in SQLite, not per-database.
        if not self._use_numpy:
            try:
                conn.enable_load_extension(True)
                import sqlite_vec
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to load sqlite-vec on new connection: %s", exc)
        return conn

    def _init(self) -> None:
        try:
            conn = self._connect()
            # Probe the extension with vec_length() + vec_version(); both
            # are guaranteed by every sqlite-vec release.
            version, = conn.execute("SELECT vec_version()").fetchone()
            _, = conn.execute(
                "SELECT vec_length(?)", [__import__("sqlite_vec").serialize_float32([0.1, 0.2, 0.3])]
            ).fetchone()
            conn.close()
            self._init_vec_schema()
            logger.info("sqlite-vec %s loaded; using ANN index.", version)
        except Exception as exc:
            logger.warning("sqlite-vec unavailable (%s).  Falling back to numpy cosine search.", exc)
            self._use_numpy = True
            self._init_fallback_schema()

    def _init_vec_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS documents("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  source TEXT NOT NULL,"
            "  domain TEXT NOT NULL,"
            "  jurisdiction TEXT NOT NULL,"
            "  citation TEXT NOT NULL,"
            "  chunk_text TEXT NOT NULL,"
            "  chunk_index INTEGER NOT NULL,"
            "  created_at TEXT NOT NULL,"
            "  UNIQUE(source, chunk_index)"
            ")"
        )
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0("
            "  embedding FLOAT[768]"
            ")"
        )
        conn.commit()
        conn.close()

    def _init_fallback_schema(self) -> None:
        conn = self._connect()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS documents("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  source TEXT NOT NULL,"
            "  domain TEXT NOT NULL,"
            "  jurisdiction TEXT NOT NULL,"
            "  citation TEXT NOT NULL,"
            "  chunk_text TEXT NOT NULL,"
            "  chunk_index INTEGER NOT NULL,"
            "  created_at TEXT NOT NULL,"
            "  UNIQUE(source, chunk_index)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS vectors("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  chunk_id INTEGER REFERENCES documents(id) ON DELETE CASCADE UNIQUE,"
            "  embedding BLOB NOT NULL"
            ")"
        )
        conn.commit()
        conn.close()
        # Reload existing vectors into memory
        conn2 = self._connect()
        for row in conn2.execute("SELECT chunk_id, embedding FROM vectors").fetchall():
            self._numpy_vectors[row[0]] = json.loads(row[1].decode())
        conn2.close()

    def init_schema(self) -> None:
        """Idempotent — schema is created in __init__."""
        return None

    def upsert_chunks(
        self,
        rows: list[dict],
        *,
        embedder: Optional[callable] = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        conn = self._connect()
        try:
            for row in rows:
                text = row["text"]
                source = row["source"]
                domain = row["domain"]
                jurisdiction = row["jurisdiction"]
                citation = row["citation"]
                chunk_index = int(row.get("chunk_index", 0))
                embedding = (embedder(text) if embedder else row.get("embedding"))
                if not embedding:
                    raise ValueError("Row missing 'embedding' and no embedder provided.")
                cur = conn.execute(
                    """INSERT INTO documents
                    (source, domain, jurisdiction, citation, chunk_text, chunk_index, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, chunk_index) DO UPDATE SET
                        domain=excluded.domain,
                        jurisdiction=excluded.jurisdiction,
                        citation=excluded.citation,
                        chunk_text=excluded.chunk_text,
                        created_at=excluded.created_at""",
                    (source, domain, jurisdiction, citation, text, chunk_index, now),
                )
                conn.commit()
                doc_id = cur.lastrowid
                if doc_id is None:
                    doc_id = conn.execute(
                        "SELECT id FROM documents WHERE source=? AND chunk_index=?",
                        (source, chunk_index),
                    ).fetchone()[0]
                if self._use_numpy:
                    self._numpy_vectors[doc_id] = embedding
                    conn.execute(
                        "INSERT OR REPLACE INTO vectors (chunk_id, embedding) VALUES (?, ?)",
                        (doc_id, _pack(embedding)),
                    )
                else:
                    # sqlite-vec virtual table: vectors are stored as
                    # float32 BLOBs.  ``sqlite_vec.serialize_float32`` packs a
                    # Python list into the exact byte layout vec0 expects.
                    from sqlite_vec import serialize_float32
                    conn.execute(
                        "INSERT OR REPLACE INTO vectors (rowid, embedding) VALUES (?, ?)",
                        (doc_id, serialize_float32(embedding)),
                    )
                conn.commit()
                count += 1
        finally:
            conn.close()
        return count

    def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        domain_filter: Optional[str] = None,
    ) -> list[dict]:
        conn = self._connect()
        try:
            if self._use_numpy:
                scored = sorted(
                    [(doc_id, _cosine(query_embedding, vec)) for doc_id, vec in self._numpy_vectors.items()],
                    key=lambda x: x[1],
                    reverse=True,
                )
                if not scored:
                    return []
                fetch_ids = [cid for cid, _ in scored[: max(k * 4, k)]]
                placeholders = ",".join("?" * len(fetch_ids))
                sql = f"SELECT * FROM documents WHERE id IN ({placeholders})"
                params: list = list(fetch_ids)
                if domain_filter:
                    sql += " AND domain = ?"
                    params.append(domain_filter)
                rows = conn.execute(sql, params).fetchall()
                id_score = {cid: s for cid, s in scored}
                results = [
                    {
                        "source": r["source"],
                        "domain": r["domain"],
                        "jurisdiction": r["jurisdiction"],
                        "citation": r["citation"],
                        "chunk_text": r["chunk_text"],
                        "similarity": id_score.get(r["id"], 0.0),
                    }
                    for r in rows
                ]
                results.sort(key=lambda x: x["similarity"], reverse=True)
                return results[:k]
            else:
                sql = """SELECT d.source, d.domain, d.jurisdiction, d.citation, d.chunk_text, distance
                    FROM vectors v JOIN documents d ON d.id = v.rowid"""
                params: list = [query_embedding, max(k * 4, k)]
                if domain_filter:
                    sql += " WHERE d.domain = ?"
                    params.append(domain_filter)
                sql += "\nORDER BY distance ASC\nLIMIT ?"
                params.append(k)
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def get_by_sources(
        self,
        source_ids: list[str],
    ) -> list[dict]:
        """Return all chunks for the given source IDs, ordered by chunk_index."""
        if not source_ids:
            return []
        conn = self._connect()
        try:
            placeholders = ",".join("?" * len(source_ids))
            sql = (
                f"SELECT source, domain, jurisdiction, citation, chunk_text, chunk_index "
                f"FROM documents WHERE source IN ({placeholders}) "
                f"ORDER BY source, chunk_index"
            )
            return [
                {
                    "source": r["source"],
                    "domain": r["domain"],
                    "jurisdiction": r["jurisdiction"],
                    "citation": r["citation"],
                    "chunk_text": r["chunk_text"],
                    "similarity": 1.0,
                }
                for r in conn.execute(sql, list(source_ids)).fetchall()
            ]
        finally:
            conn.close()

    def stats(self) -> dict:
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            sources = [
                dict(r)
                for r in conn.execute(
                    "SELECT source, domain, jurisdiction, COUNT(*) AS chunks "
                    "FROM documents GROUP BY source ORDER BY source"
                ).fetchall()
            ]
            last_row = conn.execute(
                "SELECT created_at FROM documents ORDER BY id DESC LIMIT 1"
            ).fetchone()
            last_at = last_row["created_at"] if last_row else None
        finally:
            conn.close()
        return {
            "total_chunks": total,
            "sources": sources,
            "last_refresh_at": last_at,
            "engine": "numpy_fallback" if self._use_numpy else "sqlite_vec",
        }
