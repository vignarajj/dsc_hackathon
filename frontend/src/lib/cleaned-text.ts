export function markdownForCleanedText(text: string): string {
  const body = text.replace(/\r\n/g, "\n").trimEnd();
  if (!body.trim()) {
    return "";
  }
  return body.endsWith("\n") ? body : `${body}\n`;
}

export function cleanedMarkdownName(filename: string): string {
  return `${safeStem(filename)}.cleaned.md`;
}

export function overlayPngName(filename: string): string {
  return `${safeStem(filename)}.overlay.png`;
}

export function safePngName(filename: string): string {
  return `${safeStem(filename)}.safe.png`;
}

const CATEGORY_LABELS: Record<string, string> = {
  phone: "Phone",
  email: "Email",
  id_number: "ID number",
  account_number: "Account number",
  card_number: "Card number",
  address: "Address",
  date_of_birth: "Date of birth",
  name: "Name",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category.replace(/_/g, " ");
}

function safeStem(filename: string): string {
  const leaf = filename.split(/[/\\]/).pop() ?? "";
  const stem = leaf.replace(/\.[^.]+$/, "").trim();
  const safe = stem.replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "");
  return safe || "screenshot";
}
