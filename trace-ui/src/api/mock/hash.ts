import type { AuditLogRow } from "../types";

const encoder = new TextEncoder();

export const GENESIS_HASH = "GENESIS";

export async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(input));
  const bytes = new Uint8Array(digest);
  let hex = "";
  for (let i = 0; i < bytes.length; i += 1) {
    hex += bytes[i].toString(16).padStart(2, "0");
  }
  return hex;
}

export async function computeRowHash(prevHash: string, row: AuditLogRow): Promise<string> {
  const payload = [
    prevHash,
    row.id,
    row.thread_id,
    row.company_name,
    row.metric_name,
    row.decision,
    String(row.original_value),
    String(row.corrected_value ?? ""),
    row.reviewer_notes,
    row.timestamp,
  ].join("|");
  return sha256Hex(payload);
}

export async function verifyChain(rows: AuditLogRow[]): Promise<{
  verified: boolean;
  message: string;
  total_rows: number;
  checked_rows: number;
  broken_row_id: string | null;
}> {
  let prevHash = GENESIS_HASH;
  let checked = 0;
  for (const row of rows) {
    const expected = await computeRowHash(prevHash, row);
    if (expected !== row.row_hash) {
      return {
        verified: false,
        message: `Hash chain broken at audit log row ${row.id}`,
        total_rows: rows.length,
        checked_rows: checked + 1,
        broken_row_id: row.id,
      };
    }
    prevHash = row.row_hash;
    checked += 1;
  }
  return {
    verified: true,
    message: "Audit log hash chain verified intact",
    total_rows: rows.length,
    checked_rows: checked,
    broken_row_id: null,
  };
}
