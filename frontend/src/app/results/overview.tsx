"use client";

import { useState } from "react";

import { overlayPngName } from "@/lib/cleaned-text";
import { type ProcessResponse, regionCounts } from "@/lib/process-client";

import { CompareSlider } from "./compare-slider";
import { regionLabel, swatchFor } from "./labels";

export function Overview({
  result,
  fileName,
  originalUrl,
  labels,
  custom,
}: {
  result: ProcessResponse;
  fileName: string;
  originalUrl: string;
  labels: readonly string[];
  custom: readonly string[];
}) {
  const [active, setActive] = useState<string | null>(null);
  const counts = regionCounts(result.boxes, labels);
  const overlayUrl = `data:image/png;base64,${result.overlay_png_base64}`;

  function downloadOverlay() {
    const anchor = document.createElement("a");
    anchor.href = overlayUrl;
    anchor.download = overlayPngName(fileName);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  return (
    <section
      aria-labelledby="overview"
      className="flex flex-col gap-4 rounded-3xl border border-line bg-paper p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="overview" className="font-display text-2xl font-normal">
          Regions
        </h2>
        <button
          type="button"
          onClick={downloadOverlay}
          className="rounded-full border border-line px-4 py-1.5 text-sm"
        >
          Download overlay PNG
        </button>
      </div>
      <CompareSlider
        beforeUrl={originalUrl}
        afterUrl={overlayUrl}
        beforeLabel="Original"
        afterLabel="SAM overlay"
        afterAlt="Upload with SAM masks"
        name="Compare the original with the SAM overlay"
        highlight={active ? result.boxes.filter((box) => box.label === active) : []}
        highlightColor={active ? swatchFor(active, result.palette, custom) : undefined}
      />
      {counts.length > 0 ? (
        <>
          <ul className="flex flex-wrap gap-2" aria-label="Regions found">
            {counts.map(({ label, count, bestScore }) => (
              <li key={label}>
                <button
                  type="button"
                  disabled={count === 0}
                  aria-pressed={active === label}
                  onMouseEnter={() => setActive(label)}
                  onMouseLeave={() => setActive(null)}
                  onFocus={() => setActive(label)}
                  onBlur={() => setActive(null)}
                  onClick={() => setActive((current) => (current === label ? null : label))}
                  className="flex items-center gap-2 rounded-full border border-line bg-background px-3 py-1 text-sm text-muted aria-pressed:border-foreground disabled:cursor-default"
                >
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: swatchFor(label, result.palette, custom) }}
                    aria-hidden="true"
                  />
                  <span className="text-foreground">{regionLabel(label)}</span>
                  <span>
                    {count === 0 ? "none found" : `${count} found`}
                    {bestScore !== null ? ` · best ${Math.round(bestScore * 100)}%` : ""}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">
            Point at or focus a region to outline it on the picture. Drag the slider to compare.
          </p>
        </>
      ) : (
        <p className="text-sm text-muted">No regions were requested, so the overlay has no masks.</p>
      )}
      {result.models ? (
        <p className="text-xs text-muted">
          Segmented with {result.models.segmentation}. Transcribed with{" "}
          {result.models.transcription}. Proofread with {result.models.proofread}.
          {result.models.signatures ? ` Signatures located with ${result.models.signatures}.` : ""}
        </p>
      ) : null}
    </section>
  );
}
