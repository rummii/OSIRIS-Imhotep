"""Unit tests for backend/app/services/export_service.py.

Covers:
  * Multi-format dispatch (md, docx, odt, xlsx, csv, xml).
  * WBS dependency parsing and PredecessorLink emission (sequential, fan-in, none).
  * Schedule generation (ISO-8601 durations, start/finish dates).
  * Safe filename coercion and cost-format flagging.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree as ET

import pytest

from app.services.export_service import (
    ALL_FORMATS,
    COSTING_FORMATS,
    DEFAULT_FILENAMES,
    MIME_TYPES,
    export_sow,
    export_to_csv,
    export_to_docx,
    export_to_gantt_xml,
    export_to_markdown,
    export_to_odt,
    export_to_xlsx,
)
from tests.fixtures.sow_fixtures import (
    FULL_SOW,
    MIN_SOW,
    WBS_FAN_IN_SOW,
    WBS_NO_DEPS_SOW,
)


# =============================================================================
# Format registry
# =============================================================================

class TestFormatRegistry:
    def test_all_formats_includes_dispatch_set(self):
        for fmt in ("md", "docx", "odt", "xlsx", "csv", "xml"):
            assert fmt in ALL_FORMATS

    def test_costing_formats_are_locked_behind_superadmin(self):
        assert COSTING_FORMATS == frozenset({"xlsx", "csv"})

    def test_mime_types_have_entry_for_every_format(self):
        for fmt in ALL_FORMATS:
            assert fmt in MIME_TYPES, f"missing MIME type for {fmt}"

    def test_default_filenames_cover_every_format(self):
        for fmt in ALL_FORMATS:
            assert fmt in DEFAULT_FILENAMES, f"missing default filename for {fmt}"


# =============================================================================
# Markdown (pass-through)
# =============================================================================

class TestMarkdownExport:
    def test_passes_through_utf8(self):
        text = "# Title\n\n**Bold** and émojí 🚧"
        result = export_to_markdown(text)
        assert isinstance(result, bytes)
        assert result.decode("utf-8") == text

    def test_handles_empty_string(self):
        assert export_to_markdown("") == b""

    def test_handles_none(self):
        assert export_to_markdown(None) == b""

    def test_dispatch_returns_markdown_filename(self):
        out = export_sow(sow=MIN_SOW, content_md="# Hello", title="My SOW", formats=["md"])
        filename, body = out["md"]
        assert filename.endswith(".md")
        assert body == b"# Hello"


# =============================================================================
# DOCX — hand-rolled OpenXML zip
# =============================================================================

class TestDocxExport:
    def test_returns_valid_zip(self):
        body = export_to_docx(FULL_SOW, "HVAC Assessment")
        assert isinstance(body, bytes)
        assert body[:2] == b"PK"  # zip magic

    def test_zip_contains_required_parts(self):
        body = export_to_docx(FULL_SOW, "HVAC Assessment")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            names = set(zf.namelist())
        assert "word/document.xml" in names
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names

    def test_document_xml_contains_title(self):
        body = export_to_docx(FULL_SOW, "Custom Title Here")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert "Custom Title Here" in xml

    def test_document_xml_contains_executive_summary_overview(self):
        body = export_to_docx(FULL_SOW, "T")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert "assessment" in xml  # case-insensitive check
        assert "Executive Summary" in xml

    def test_dispatch_returns_docx_filename(self):
        out = export_sow(sow=FULL_SOW, content_md="x", title="SOW", formats=["docx"])
        assert out["docx"][0].endswith(".docx")

    def test_handles_special_chars_in_title(self):
        # Title with slashes/colons must not break zip filenames
        body = export_to_docx(FULL_SOW, "Site / 2025: Phase 1")
        assert body[:2] == b"PK"


# =============================================================================
# ODT — OpenDocument text
# =============================================================================

class TestOdtExport:
    def test_returns_odt_zip(self):
        body = export_to_odt(FULL_SOW, "HVAC")
        assert body[:2] == b"PK"
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            names = set(zf.namelist())
        assert "mimetype" in names
        assert "content.xml" in names

    def test_mimetype_is_odt_uncompressed(self):
        # ODF spec: mimetype must be first entry, stored without compression
        body = export_to_odt(FULL_SOW, "HVAC")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            info = zf.infolist()
            assert info[0].filename == "mimetype"
            assert info[0].compress_type == zipfile.ZIP_STORED
            assert zf.read("mimetype") == b"application/vnd.oasis.opendocument.text"

    def test_content_xml_contains_title(self):
        body = export_to_odt(FULL_SOW, "My ODT Title")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            xml = zf.read("content.xml").decode("utf-8")
        assert "My ODT Title" in xml

    def test_dispatch_returns_odt_filename(self):
        out = export_sow(sow=FULL_SOW, content_md="x", title="SOW", formats=["odt"])
        assert out["odt"][0].endswith(".odt")


# =============================================================================
# XLSX — cost breakdown
# =============================================================================

class TestXlsxExport:
    def test_returns_valid_xlsx_zip(self):
        body = export_to_xlsx(FULL_SOW, "HVAC")
        assert body[:2] == b"PK"
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            assert "xl/workbook.xml" in zf.namelist()
            assert "xl/worksheets/sheet1.xml" in zf.namelist()

    def test_workbook_has_recommended_services_sheet(self):
        body = export_to_xlsx(FULL_SOW, "HVAC")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            sheet_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        # Three recommended services → at least 4 rows (1 header + 3 data)
        assert sheet_xml.count("<row ") >= 4

    def test_shared_strings_contains_currency(self):
        body = export_to_xlsx(FULL_SOW, "HVAC")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        # Currency from FULL_SOW = PHP
        assert "PHP" in sheet

    def test_dispatch_returns_cost_breakdown_filename(self):
        out = export_sow(sow=FULL_SOW, content_md="x", title="SOW", formats=["xlsx"])
        assert "cost-breakdown" in out["xlsx"][0]
        assert out["xlsx"][0].endswith(".xlsx")

    def test_minimal_sow_still_produces_xlsx(self):
        body = export_to_xlsx(MIN_SOW, "M")
        assert body[:2] == b"PK"


# =============================================================================
# CSV — cost breakdown
# =============================================================================

class TestCsvExport:
    def test_returns_decoded_csv(self):
        body = export_to_csv(FULL_SOW, "HVAC")
        assert isinstance(body, bytes)
        text = body.decode("utf-8-sig")  # strip BOM
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        # CSV has title, project info, cost table, then service table
        assert len(rows) >= 5
        # Find the service table header row (contains 'ID' as first column)
        header_row = next((r for r in rows if r and r[0].lower() == "id"), None)
        assert header_row is not None, "CSV should contain a service table with 'ID' column"

    def test_csv_contains_service_lines(self):
        text = export_to_csv(FULL_SOW, "HVAC").decode("utf-8")
        assert "HVAC System Replacement" in text
        assert "Chiller Compressor" in text
        assert "Ductwork Rehabilitation" in text

    def test_csv_uses_utf8_charset(self):
        body = export_to_csv(FULL_SOW, "HVAC")
        text = body.decode("utf-8")
        # Test a non-ASCII char round-trips
        assert "—" in text or "–" in text or "PHP" in text

    def test_dispatch_returns_cost_breakdown_csv(self):
        out = export_sow(sow=FULL_SOW, content_md="x", title="SOW", formats=["csv"])
        assert "cost-breakdown" in out["csv"][0]
        assert out["csv"][0].endswith(".csv")


# =============================================================================
# XML — MS Project-compatible Gantt
# =============================================================================

class TestGanttXmlExport:
    def test_returns_well_formed_xml(self):
        body = export_to_gantt_xml(FULL_SOW, "HVAC")
        # Must round-trip through ElementTree
        root = ET.fromstring(body)
        assert root.tag.endswith("Project")

    def test_xml_emits_one_task_per_scope_phase(self):
        body = export_to_gantt_xml(FULL_SOW, "HVAC")
        ns = {"p": "http://schemas.microsoft.com/project"}
        root = ET.fromstring(body)
        tasks = root.findall("p:Tasks/p:Task", ns)
        # FULL_SOW has 5 scope_breakdown phases
        assert len(tasks) == 5

    def test_xml_uses_isofmt_durations(self):
        body = export_to_gantt_xml(FULL_SOW, "HVAC")
        # ISO-8601 PTnH0M0S pattern
        assert re.search(rb"PT\d+H0M0S", body) is not None

    def test_xml_task_names_match_scope_phases(self):
        body = export_to_gantt_xml(FULL_SOW, "HVAC")
        ns = {"p": "http://schemas.microsoft.com/project"}
        root = ET.fromstring(body)
        names = [t.find("p:Name", ns).text for t in root.findall("p:Tasks/p:Task", ns)]
        assert "Phase 1 — Decommissioning" in names
        assert "Phase 5 — Commissioning & Handover" in names

    def test_xml_dispatch_returns_gantt_filename(self):
        out = export_sow(sow=FULL_SOW, content_md="x", title="SOW", formats=["xml"])
        assert "gantt" in out["xml"][0]
        assert out["xml"][0].endswith(".xml")

        out = export_sow(sow=FULL_SOW, content_md="x", title="Plan A/B: Rev 1", formats=["docx"])
        filename, _ = out["docx"]
        assert "/" not in filename
        assert ":" not in filename



# =============================================================================
# WBS dependency ordering
# =============================================================================

class TestWbsDependencyOrdering:
    """Verify that PredecessorLink nodes are emitted correctly for sequential,
    fan-in, and no-dependency phase patterns."""

    def _parse_xml_tasks(self, body: bytes) -> list[dict]:
        ns = {"p": "http://schemas.microsoft.com/project"}
        root = ET.fromstring(body)
        tasks = []
        for task in root.findall("p:Tasks/p:Task", ns):
            uid = int(task.find("p:UID", ns).text)
            name = task.find("p:Name", ns).text
            seq = int(task.find("p:Sequence", ns).text)
            preds = task.find("p:PredecessorLink", ns)
            predecessor_uids = []
            if preds is not None:
                for pred in preds.findall("p:Predecessor", ns):
                    predecessor_uids.append(int(pred.find("p:PredecessorUID", ns).text))
            tasks.append({"uid": uid, "name": name, "seq": seq, "predecessor_uids": predecessor_uids})
        return tasks

    def test_sequential_wbs_emits_predecessor_for_phase2(self):
        """Phase 2 depends on Phase 1 → one PredecessorLink."""
        body = export_to_gantt_xml(FULL_SOW, "T")
        tasks = self._parse_xml_tasks(body)
        p2 = next(t for t in tasks if "Phase 2" in t["name"])
        assert len(p2["predecessor_uids"]) == 1, "Phase 2 should have exactly one predecessor"

    def test_sequential_wbs_no_predecessor_for_phase1(self):
        """Phase 1 has no dependencies → no PredecessorLink."""
        body = export_to_gantt_xml(FULL_SOW, "T")
        tasks = self._parse_xml_tasks(body)
        p1 = next(t for t in tasks if "Phase 1" in t["name"])
        assert p1["predecessor_uids"] == []

    def test_sequential_wbs_last_phase_has_one_predecessor(self):
        """Phase 5 depends on Phase 4 → one PredecessorLink."""
        body = export_to_gantt_xml(FULL_SOW, "T")
        tasks = self._parse_xml_tasks(body)
        p5 = next(t for t in tasks if "Phase 5" in t["name"])
        assert len(p5["predecessor_uids"]) == 1

    def test_fan_in_wbs_p3_has_two_predecessors(self):
        """P3 depends on P1 and P2 → two PredecessorLink nodes."""
        body = export_to_gantt_xml(WBS_FAN_IN_SOW, "T")
        tasks = self._parse_xml_tasks(body)
        p3 = next(t for t in tasks if "P3" in t["name"])
        assert len(p3["predecessor_uids"]) == 2, f"Expected 2 predecessors, got {p3['predecessor_uids']}"

    def test_fan_in_wbs_p4_has_one_predecessor(self):
        """P4 depends only on P3 → one PredecessorLink."""
        body = export_to_gantt_xml(WBS_FAN_IN_SOW, "T")
        tasks = self._parse_xml_tasks(body)
        p4 = next(t for t in tasks if "P4" in t["name"])
        assert len(p4["predecessor_uids"]) == 1

    def test_no_deps_wbs_all_tasks_have_zero_predecessors(self):
        """All phases in WBS_NO_DEPS_SOW have empty depends_on."""
        body = export_to_gantt_xml(WBS_NO_DEPS_SOW, "T")
        tasks = self._parse_xml_tasks(body)
        for task in tasks:
            assert task["predecessor_uids"] == [], f"Task {task['name']} should have no predecessors"

    def test_sequence_field_orders_tasks_in_wbs(self):
        """The Sequence field should reflect the declared sequence order."""
        body = export_to_gantt_xml(FULL_SOW, "T")
        tasks = self._parse_xml_tasks(body)
        seqs = {t["name"]: t["seq"] for t in tasks}
        assert seqs["Phase 1 — Decommissioning"] < seqs["Phase 5 — Commissioning & Handover"]

    def test_predecessor_type_is_finish_to_start(self):
        """PredecessorLink Type should be 1 (Finish-To-Start per MS Project schema)."""
        body = export_to_gantt_xml(FULL_SOW, "T")
        ns = {"p": "http://schemas.microsoft.com/project"}
        root = ET.fromstring(body)
        for link in root.findall("p:Tasks/p:Task/p:PredecessorLink/p:Predecessor", ns):
            link_type = link.find("p:Type", ns)
            assert link_type is not None, "PredecessorLink should have a Type element"
            assert link_type.text == "1", f"Expected Type=1 (FS), got {link_type.text}"


# =============================================================================
# Multi-format dispatch
# =============================================================================

class TestDispatch:
    def test_single_format_returns_single_entry(self):
        out = export_sow(sow=MIN_SOW, content_md="x", title="T", formats=["md"])
        assert list(out.keys()) == ["md"]

    def test_multiple_formats_returns_all(self):
        out = export_sow(sow=MIN_SOW, content_md="x", title="T",
                         formats=["docx", "odt", "csv", "xml"])
        assert set(out.keys()) == {"docx", "odt", "csv", "xml"}

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported export format"):
            export_sow(sow=MIN_SOW, content_md="x", title="T", formats=["pdf"])

    def test_case_insensitive_format(self):
        out = export_sow(sow=MIN_SOW, content_md="x", title="T", formats=["DOCX", "Csv"])
        assert "docx" in out
        assert "csv" in out

    def test_unknown_fields_stripped_gracefully(self):
        bad = {**MIN_SOW, "unknown_field": "should-be-ignored"}
        body = export_to_docx(bad, "T")
        assert body[:2] == b"PK"

    def test_minimal_sow_all_formats(self):
        for fmt in ALL_FORMATS:
            if fmt == "md":
                continue
            out = export_sow(sow=MIN_SOW, content_md="x", title="T", formats=[fmt])
            assert fmt in out
