// TypeScript mirror of backend/app/models/schemas.py

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
}

export interface ExportResponse {
  doc_url: string;
  doc_id: string;
}

export interface AttachedMedia {
  id: string;
  name: string;
  size: number;
  kind: "image" | "video" | "unknown";
  file: File;
  previewUrl: string;
}
