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

function safeStem(filename: string): string {
  const leaf = filename.split(/[/\\]/).pop() ?? "";
  const stem = leaf.replace(/\.[^.]+$/, "").trim();
  const safe = stem.replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "");
  return safe || "screenshot";
}
