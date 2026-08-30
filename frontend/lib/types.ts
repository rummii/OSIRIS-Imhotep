// Type definitions mirrored from the SOW API

export interface ExecutiveSummary {
  overview: string;
  overall_condition: string;
  priority_findings?: string | null;
}

export interface VisualFinding {
  id: string;
  asset: string;
  location: string;
  condition: string;
  severity: string;
  description: string;
  oem_reference?: string | null;
  recommended_action: string;
}

export interface RecommendedService {
  id: string;
  service: string;
  asset: string;
  priority: string;
  quantity: number;
  unit: string;
  unit_cost: number;
  total_cost: number;
  notes?: string | null;
}

export interface ScopeItem {
  phase: string;
  work_description: string;
  deliverables: string[];
  duration_days: number;
}

export interface CostBreakdown {
  currency: string;
  labor: number;
  materials: number;
  equipment: number;
  subtotal: number;
  contingency_pct: number;
  contingency: number;
  total: number;
}

export interface SowResponse {
  project_title: string;
  site?: string | null;
  client?: string | null;
  generated_at: string;
  currency: string;
  /** Fallback summary used by older/legacy saved docs that lack executive_summary. */
  scope_summary?: string;
  executive_summary: ExecutiveSummary;
  visual_findings: VisualFinding[];
  recommended_services: RecommendedService[];
  scope_breakdown: ScopeItem[];
  cost_breakdown: CostBreakdown;
}

export interface GroundingSource {
  title: string;
  url: string;
}

export interface MediaLogEntry {
  filename: string;
  kind: string;
  status: string;
  detail: string;
  frames: number;
}

export interface GenerateResponse {
  sow: SowResponse;
  media_log: MediaLogEntry[];
  model: string;
  grounding: boolean;
  grounding_sources: GroundingSource[];
  context_provider: string;
  generated_at: string;
  document_id?: number | null;
  spatial_context?: SpatialManifest | null;
}

export interface SpatialContext {
  latitude?: number | null;
  longitude?: number | null;
  altitude_m?: number | null;
  accuracy_m?: number | null;
  captured_at?: string | null;
  source_file: string;
  site_location?: SiteLocation | null;  // Phase 3: reverse-geocoded PSGC location
}

export interface SiteLocation {
  barangay?: string | null;
  municipality?: string | null;
  province?: string | null;
  region?: string | null;
  country?: string | null;
  raw_address?: string | null;
}

export interface SpatialManifest {
  files: Record<string, SpatialContext | null>;
}

export interface ExportResponse {
  doc_url: string;
  doc_id: string;
}

/**
 * Feature-gate config served by `GET /api/admin/config` (superadmin only).
 *
 * The frontend uses these flags to hide or disable export options whose
 * server-side counterparts would 403 anyway. `undefined` while the config
 * is still loading — callers should treat that as "use the safer default"
 * (e.g. assume the gate is closed so we don't accidentally expose a
 * disabled export).
 */
export interface ExportConfig {
  export_costing_enabled: boolean;
}

export interface AttachedMedia {
  id: string;
  name: string;
  size: number;
  kind: "image" | "video" | "unknown";
  file: File;
  previewUrl: string;
}

export type ExportFormat = "docx" | "odt" | "xlsx" | "csv" | "xml" | "md" | "json";

export interface ExportFormatMeta {
  label: string;
  ext: string;
  mime: string;
  requiresSuperadmin: boolean;
}

export const EXPORT_FORMATS: Record<ExportFormat, ExportFormatMeta> = {
  docx: { label: "Word",        ext: ".docx", mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", requiresSuperadmin: false },
  odt:  { label: "LibreOffice", ext: ".odt",  mime: "application/vnd.oasis.opendocument.text",                               requiresSuperadmin: false },
  xlsx: { label: "Excel",        ext: ".xlsx", mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",   requiresSuperadmin: true  },
  csv:  { label: "CSV",          ext: ".csv",  mime: "text/csv; charset=utf-8",                                              requiresSuperadmin: true  },
  xml:  { label: "MS Project",   ext: ".xml",  mime: "application/xml; charset=utf-8",                                       requiresSuperadmin: false },
  md:   { label: "Markdown",     ext: ".md",   mime: "text/markdown; charset=utf-8",                                         requiresSuperadmin: false },
  json: { label: "JSON",         ext: ".json", mime: "application/json",                                                       requiresSuperadmin: false },
};
