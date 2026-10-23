import type { DocumentField, ProcessResponse } from "./process-client";

const DOCUMENT_TYPES: Record<string, string> = {
  invoice: "Invoice",
  receipt: "Receipt",
  form: "Form",
  id_document: "ID document",
  letter: "Letter",
  chat: "Chat",
  note: "Note",
  screenshot: "Screenshot",
  other: "Other",
};

export function documentTypeLabel(type: string): string {
  return DOCUMENT_TYPES[type] ?? type.replace(/_/g, " ");
}

/** The fields, regions, and text of one result, for the JSON download. */
export function dataJson(result: ProcessResponse, fileName: string): string {
  return `${JSON.stringify(
    {
      file: fileName,
      document: result.document,
      regions: result.boxes,
      text: { transcription: result.original_text, proofread: result.cleaned_text },
    },
    null,
    2,
  )}\n`;
}

/** label,value rows. Every cell is quoted, and a cell a spreadsheet would run as a formula is defused. */
export function fieldsCsv(fields: readonly DocumentField[]): string {
  const rows = [["label", "value"], ...fields.map((field) => [field.label, field.value])];
  const lines = rows.map((row, index) => (index === 0 ? row : row.map(csvCell)).join(","));
  return `${lines.join("\r\n")}\r\n`;
}

function csvCell(value: string): string {
  // A leading = + - @ tab or carriage return starts a formula in Excel and Sheets.
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return `"${safe.replace(/"/g, '""')}"`;
}
