import { CUSTOM_PALETTE, REGION_CONCEPTS } from "@/lib/process-client";

export type RegionId = (typeof REGION_CONCEPTS)[number];

export const REGION_LABELS: Record<RegionId, { label: string; swatch: string }> = {
  stamp: { label: "Stamp", swatch: "#dc2626" },
  signature: { label: "Signature", swatch: "#2563eb" },
  photograph: { label: "Photograph", swatch: "#ea580c" },
  rectangle: { label: "Rectangle", swatch: "#16a34a" },
};

export function regionLabel(label: string): string {
  const known = REGION_LABELS[label as RegionId];
  if (known) {
    return known.label;
  }
  const words = label.replace(/^qr\b/, "QR");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The legend color: the preset's, then the API palette, then the order the user typed. */
export function swatchFor(
  label: string,
  palette: Record<string, string> | undefined,
  custom: readonly string[],
): string {
  const known = REGION_LABELS[label as RegionId];
  if (known) {
    return known.swatch;
  }
  const index = Math.max(0, custom.indexOf(label));
  return palette?.[label] ?? CUSTOM_PALETTE[index % CUSTOM_PALETTE.length];
}
