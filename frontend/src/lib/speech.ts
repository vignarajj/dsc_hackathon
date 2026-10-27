const MAX_CHUNK_CHARS = 200;

/**
 * Split text into pieces short enough to speak one at a time.
 *
 * Chrome stops a long utterance part way through, so the text is cut at
 * sentence ends, then at commas or spaces when a sentence is still too long.
 */
export function speechChunks(text: string, max: number = MAX_CHUNK_CHARS): string[] {
  const sentences = text
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?…])\s+/)
    .filter(Boolean);
  const chunks: string[] = [];
  for (const sentence of sentences) {
    let rest = sentence;
    while (rest.length > max) {
      const head = rest.slice(0, max);
      const cut = Math.max(head.lastIndexOf(", "), head.lastIndexOf(" "));
      const at = cut > max / 3 ? cut + 1 : max;
      chunks.push(rest.slice(0, at).trim());
      rest = rest.slice(at).trim();
    }
    if (rest) {
      chunks.push(rest);
    }
  }
  return chunks;
}
