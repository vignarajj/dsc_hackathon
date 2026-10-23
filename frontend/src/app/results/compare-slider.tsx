"use client";

import { useState } from "react";

export type HighlightBox = { x: number; y: number; w: number; h: number };

/** The "before" picture left of the handle, the "after" picture right of it. */
export function CompareSlider({
  beforeUrl,
  afterUrl,
  beforeLabel,
  afterLabel,
  afterAlt,
  name,
  highlight = [],
  highlightColor = "currentColor",
}: {
  beforeUrl: string;
  afterUrl: string;
  beforeLabel: string;
  afterLabel: string;
  afterAlt: string;
  name: string;
  highlight?: readonly HighlightBox[];
  highlightColor?: string;
}) {
  const [split, setSplit] = useState(50);
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-center rounded-2xl bg-background">
        {/* The frame hugs the picture, so the handle and boxes map onto it. */}
        <div className="relative max-w-full overflow-hidden">
          {/* Both are data or object URLs, so the image optimizer cannot fetch them. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={afterUrl}
            alt={afterAlt}
            onLoad={(event) =>
              setNatural({
                w: event.currentTarget.naturalWidth,
                h: event.currentTarget.naturalHeight,
              })
            }
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
          {natural
            ? highlight.map((box, index) => (
                <div
                  key={index}
                  data-testid="highlight"
                  aria-hidden="true"
                  className="pointer-events-none absolute rounded-sm"
                  style={{
                    left: `${(box.x / natural.w) * 100}%`,
                    top: `${(box.y / natural.h) * 100}%`,
                    width: `${(box.w / natural.w) * 100}%`,
                    height: `${(box.h / natural.h) * 100}%`,
                    outline: `3px solid ${highlightColor}`,
                    outlineOffset: "2px",
                  }}
                />
              ))
            : null}
        </div>
      </div>
      <label className="flex items-center gap-3 text-sm text-muted">
        <span className="shrink-0">{beforeLabel}</span>
        <input
          type="range"
          min={0}
          max={100}
          value={split}
          onChange={(event) => setSplit(Number(event.target.value))}
          onKeyDown={(event) => {
            if (event.key === "Home" || event.key === "End") {
              event.preventDefault();
              setSplit(event.key === "Home" ? 0 : 100);
            }
          }}
          aria-label={name}
          aria-valuetext={`${split}% ${beforeLabel}`}
          className="w-full accent-stamp"
        />
        <span className="shrink-0">{afterLabel}</span>
      </label>
    </div>
  );
}
