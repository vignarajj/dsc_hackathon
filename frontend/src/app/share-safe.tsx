"use client";

import { useState } from "react";

import { categoryLabel, safePngName } from "@/lib/cleaned-text";
import type { ProcessResponse } from "@/lib/process-client";

export function ShareSafe({
  result,
  fileName,
  originalUrl,
}: {
  result: ProcessResponse;
  fileName: string;
  originalUrl: string;
}) {
  const [notice, setNotice] = useState<string | null>(null);
  const redactedUrl = result.redacted_png_base64
    ? `data:image/png;base64,${result.redacted_png_base64}`
    : null;
  const shareable = result.shareable_text;
  if (!redactedUrl && shareable === null) {
    return null;
  }

  async function copyShareable() {
    if (!shareable) {
      return;
    }
    try {
      await navigator.clipboard.writeText(shareable);
      setNotice("Copied");
    } catch {
      setNotice("Could not copy. Select the text and copy it manually.");
    }
  }

  function downloadImage() {
    if (!redactedUrl) {
      return;
    }
    const anchor = document.createElement("a");
    anchor.href = redactedUrl;
    anchor.download = safePngName(fileName);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  return (
    <section
      aria-labelledby="share-safe"
      className="flex flex-col gap-5 rounded-3xl border border-line bg-paper p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="share-safe" className="font-display text-2xl font-normal">
          Share-safe copy
        </h2>
        {notice ? (
          <span role="status" className="text-sm text-muted">
            {notice}
          </span>
        ) : null}
      </div>

      {redactedUrl ? (
        <div className="flex flex-col gap-3">
          <CompareSlider beforeUrl={originalUrl} afterUrl={redactedUrl} />
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={downloadImage}
              className="rounded-full border border-line px-4 py-1.5 text-sm"
            >
              Download share-safe image
            </button>
            <p className="text-sm text-muted">
              {result.image_text_hidden
                ? "Sensitive text found in the picture is blacked out too. Location and camera data are removed."
                : "Text inside the picture is not hidden. Share the text version for that. Location and camera data are removed."}
            </p>
          </div>
        </div>
      ) : null}

      {shareable !== null ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
              Shareable text
            </h3>
            <button
              type="button"
              onClick={() => void copyShareable()}
              disabled={!shareable.trim()}
              className="rounded-full border border-line px-4 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
            >
              Copy shareable text
            </button>
          </div>
          <pre className="min-h-20 overflow-auto rounded-2xl border border-line bg-background p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
            {shareable.trim() ? shareable : "No text was found in this image."}
          </pre>
          {result.sensitive.length > 0 ? (
            <ul className="flex flex-wrap gap-2" aria-label="Personal details found">
              {result.sensitive.map((item) => (
                <li
                  key={`${item.category}:${item.text}`}
                  className="flex items-center gap-2 rounded-full border border-line bg-background px-3 py-1 text-sm"
                >
                  <span className="text-[11px] font-medium tracking-[0.12em] text-stamp uppercase">
                    {categoryLabel(item.category)}
                  </span>
                  <span className="max-w-[16rem] truncate">{item.text}</span>
                </li>
              ))}
            </ul>
          ) : shareable.trim() ? (
            <p className="text-sm text-muted">No personal details were found in the text.</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/** Original on the left of the handle, share-safe copy on the right. */
function CompareSlider({ beforeUrl, afterUrl }: { beforeUrl: string; afterUrl: string }) {
  const [split, setSplit] = useState(50);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-center rounded-2xl bg-background">
        {/* The frame hugs the picture, so the handle position maps onto it. */}
        <div className="relative max-w-full overflow-hidden">
          {/* Both are data or object URLs, so the image optimizer cannot fetch them. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={afterUrl}
            alt="Share-safe copy"
            className="block h-auto max-h-[36rem] w-auto max-w-full"
          />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={beforeUrl}
            alt=""
            aria-hidden="true"
            className="absolute inset-0 h-full w-full"
            style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 w-0.5 -translate-x-1/2 bg-stamp"
            style={{ left: `${split}%` }}
          />
        </div>
      </div>
      <label className="flex items-center gap-3 text-sm text-muted">
        <span className="shrink-0">Original</span>
        <input
          type="range"
          min={0}
          max={100}
          value={split}
          onChange={(event) => setSplit(Number(event.target.value))}
          aria-label="Compare the original with the share-safe copy"
          aria-valuetext={`${split}% original`}
          className="w-full accent-stamp"
        />
        <span className="shrink-0">Share-safe</span>
      </label>
    </div>
  );
}
