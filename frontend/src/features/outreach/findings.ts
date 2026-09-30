import type { Audit, AuditFinding, AuditReportItem } from "../../types/audit";

export type FindingLine = {
  title: string;
  detail: string;
};

export function findingLines(audit: Audit | undefined): FindingLine[] {
  if (!audit || audit.status !== "COMPLETED") {
    return [];
  }
  const report = audit.raw_analysis?.report;
  if (report && report.length > 0) {
    return report.slice(0, 5).map((item) => lineFromReport(item));
  }
  return audit.issues.slice(0, 5).map((item) => lineFromIssue(item));
}

function lineFromReport(item: AuditReportItem): FindingLine {
  return {
    title: item.title,
    detail: sentence(item.detail || item.title),
  };
}

function lineFromIssue(item: AuditFinding): FindingLine {
  return {
    title: item.title,
    detail: sentence(item.detail || item.title),
  };
}

function sentence(text: string): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return "";
  }
  return ".!?".includes(cleaned.at(-1) ?? "") ? cleaned : `${cleaned}.`;
}
