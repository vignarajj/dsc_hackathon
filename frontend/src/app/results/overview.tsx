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
  const [note, setNote] = useState<number | null>(null);
  const described = result.boxes
    .map((box, index) => ({ box, index }))
    .filter(({ box }) => box.description !== null);
  const highlight =
    note !== null
      ? [{ ...result.boxes[note], note: result.boxes[note].description }]
      : active
        ? result.boxes.filter((box) => box.label === active)
        : [];
  const highlightLabel = note !== null ? result.boxes[note].label : active;
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
        <h2 id="overview" className="text-xl font-semibold tracking-tight">
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
        highlight={highlight}
        highlightColor={
          highlightLabel ? swatchFor(highlightLabel, result.palette, custom) : undefined
        }
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
          {described.length > 0 ? (
            <div className="flex flex-col gap-2">
              <h3 className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
                Region notes by Muse
              </h3>
              <ul className="flex flex-col gap-1" aria-label="Region notes">
                {described.map(({ box, index }) => (
                  <li key={index}>
                    <button
                      type="button"
                      aria-pressed={note === index}
                      onMouseEnter={() => setNote(index)}
                      onMouseLeave={() => setNote(null)}
                      onFocus={() => setNote(index)}
                      onBlur={() => setNote(null)}
                      onClick={() => setNote((current) => (current === index ? null : index))}
                      className="flex w-full items-start gap-2 rounded-xl px-2 py-1.5 text-left text-sm hover:bg-background aria-pressed:bg-background"
                    >
                      <span
                        className="mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: swatchFor(box.label, result.palette, custom) }}
                        aria-hidden="true"
                      />
                      <span className="shrink-0 text-muted">{regionLabel(box.label)}</span>
                      <span>{box.description}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
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
