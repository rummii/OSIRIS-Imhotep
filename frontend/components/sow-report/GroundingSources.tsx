"use client";
// Optional: RAG/regulatory grounding source list. Only renders when at least
// one source is present.
import { FileSpreadsheet } from "lucide-react";
import { SectionTitle } from "./SectionTitle";

export function GroundingSources({ sources }: { sources: { title: string; url: string }[] }) {
  if (sources.length === 0) return null;
  return (
    <div className="card p-5 space-y-2">
      <SectionTitle icon={<FileSpreadsheet size={14} />}>Grounding Sources</SectionTitle>
      <ul className="space-y-1">
        {sources.map((source, index) => (
          <li key={index} className="text-xs">
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="text-sky-400 hover:text-sky-300 hover:underline break-all"
            >
              {source.title || source.url}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
