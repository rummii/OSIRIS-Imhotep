// Shared types for the SowReport sub-component tree.
import type { SowResponse } from "@/lib/types";

export interface SowReportProps {
  sow: SowResponse;
  model: string;
  grounding: boolean;
  groundingSources: { title: string; url: string }[];
}
