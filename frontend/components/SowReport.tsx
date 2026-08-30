// Thin re-export shim to preserve existing import paths
// (e.g. @/components/SowReport) while the real implementation
// lives in the sow-report/ sub-directory.
export type { SowReportProps } from "./sow-report";
export { default } from "./sow-report";
