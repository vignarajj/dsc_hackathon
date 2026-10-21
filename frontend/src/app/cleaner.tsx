"use client";

import { useEffect, useState, type DragEvent, type FormEvent } from "react";

import { cleanedMarkdownName, markdownForCleanedText } from "@/lib/cleaned-text";
import { processImage, type ProcessResponse, validateImageFile } from "@/lib/process-client";

type Status = "idle" | "loading" | "done" | "error";

const MASK_LEGEND = [
  { label: "Stamp", swatch: "#dc2626" },
  { label: "Signature", swatch: "#2563eb" },
  { label: "Photograph", swatch: "#ea580c" },
  { label: "Rectangle", swatch: "#16a34a" },
] as const;

const STEPS = [
  "Choose a JPEG or PNG up to 10 MB. A page photo, a chat, or a phone screenshot all work.",
  "Press Clean screenshot. Reading the image can take up to a minute.",
  "Compare the original with the overlay. Each kind of region has its own color.",
  "Copy the cleaned text, or download it as Markdown.",
] as const;

export function Cleaner({ apiBase }: { apiBase: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  function chooseFile(next: File | null) {
    setResult(null);
    setNotice(null);
    if (!next) {
      setFile(null);
      setPreviewUrl(null);
      setError(null);
      setStatus("idle");
      return;
    }
    const problem = validateImageFile(next);
    if (problem) {
      setFile(null);
      setPreviewUrl(null);
      setError(problem);
      setStatus("error");
      return;
    }
    setFile(next);
    setPreviewUrl(URL.createObjectURL(next));
    setError(null);
    setStatus("idle");
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    if (status === "loading") {
      return;
    }
    chooseFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      return;
    }
    setStatus("loading");
    setError(null);
    setNotice(null);
    setResult(null);
    try {
      const processed = await processImage(file, apiBase);
      setResult(processed);
      setStatus("done");
    } catch (caught) {
      setStatus("error");
      setError(caught instanceof Error ? caught.message : "The model request failed");
    }
  }

  const cleaned = result?.cleaned_text ?? "";
  const hasText = cleaned.trim().length > 0;

  async function copyText() {
    if (!hasText) {
      return;
    }
    try {
      await navigator.clipboard.writeText(cleaned);
      setNotice("Copied");
      setError(null);
    } catch {
      setNotice(null);
      setError("Could not copy the text. Select it and copy it manually.");
    }
  }

  function downloadText() {
    if (!hasText || !file) {
      return;
    }
    const blob = new Blob([markdownForCleanedText(cleaned)], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = cleanedMarkdownName(file.name);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 py-8 sm:px-8 sm:py-12">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-5">
        <p className="text-[11px] font-medium tracking-[0.22em] text-muted uppercase">
          Document screenshot cleaner
        </p>
        <p className="text-xs text-muted">SAM 3.1 and Muse Spark</p>
      </header>

      <div className="mt-10 grid items-end gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="flex flex-col gap-5">
          <h1 className="font-display max-w-xl text-5xl leading-[0.95] font-normal tracking-tight text-balance sm:text-6xl">
            A messy page, read cleanly.
          </h1>
          <p className="max-w-md text-[15px] leading-relaxed text-muted">
            Upload one JPEG or PNG. SAM 3.1 marks stamps, signatures, photos, and rectangles.
            Muse Spark transcribes the page and proofreads the text.
          </p>
        </div>

        <section aria-labelledby="how-to">
          <h2 id="how-to" className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
            How to use it
          </h2>
          <ol className="mt-4 grid gap-3 sm:grid-cols-2">
            {STEPS.map((step, index) => (
              <li key={step} className="rounded-2xl border border-line bg-paper px-4 py-3">
                <span className="font-display text-lg text-stamp">{index + 1}</span>
                <p className="mt-1 text-sm leading-relaxed text-muted">{step}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <form onSubmit={onSubmit} className="mt-10 flex flex-col gap-4" aria-busy={status === "loading"}>
        <label
          onDragOver={(event) => {
            event.preventDefault();
            if (status !== "loading") {
              setDragging(true);
            }
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center gap-3 rounded-3xl border border-dashed px-6 py-10 text-center transition-colors ${
            dragging ? "border-stamp bg-paper" : "border-line bg-paper/60"
          }`}
        >
          <span className="text-sm font-medium">Screenshot</span>
          <span className="max-w-sm text-sm text-muted">
            Drop a JPEG or PNG here, or choose a file. 10 MB at most.
          </span>
          {file && previewUrl ? (
            <span className="mt-2 flex items-center gap-3 rounded-2xl border border-line bg-background px-3 py-2 text-left">
              {/* The file is a local object URL, so the image optimizer cannot fetch it. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previewUrl} alt="" className="h-14 w-14 rounded-lg object-cover" />
              <span className="text-sm">{file.name}</span>
            </span>
          ) : null}
          <input
            type="file"
            name="image"
            accept="image/png,image/jpeg"
            disabled={status === "loading"}
            onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
            className="sr-only"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={!file || status === "loading"}
            className="rounded-full border border-stamp bg-stamp px-5 py-2.5 text-sm font-medium text-stamp-ink disabled:cursor-not-allowed disabled:border-line disabled:bg-transparent disabled:text-muted"
          >
            {status === "loading" ? "Cleaning…" : "Clean screenshot"}
          </button>
        </div>
      </form>

      {status === "loading" ? (
        <div className="mt-6">
          <div className="reading-bar w-full" />
          <p role="status" className="mt-3 text-sm text-muted">
            Reading the image. This can take up to a minute.
          </p>
        </div>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="mt-6 rounded-2xl border border-stamp/40 bg-paper px-4 py-3 text-sm text-stamp"
        >
          {error}
        </p>
      ) : null}

      {status === "done" && result && previewUrl ? (
        <section className="mt-10 flex flex-col gap-6">
          <div className="grid items-start gap-4 md:grid-cols-2">
            <figure className="flex flex-col gap-3 rounded-3xl border border-line bg-paper p-4">
              <figcaption className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
                Original
              </figcaption>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Original upload"
                className="max-h-[32rem] w-full rounded-2xl bg-background object-contain"
              />
            </figure>
            <figure className="flex flex-col gap-3 rounded-3xl border border-line bg-paper p-4">
              <figcaption className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
                SAM overlay
              </figcaption>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${result.overlay_png_base64}`}
                alt="Upload with SAM masks"
                className="max-h-[32rem] w-full rounded-2xl bg-background object-contain"
              />
            </figure>
          </div>
          <ul className="flex flex-wrap gap-2">
            {MASK_LEGEND.map((item) => (
              <li
                key={item.label}
                className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1 text-sm text-muted"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: item.swatch }}
                  aria-hidden="true"
                />
                {item.label}
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-4 rounded-3xl border border-line bg-paper p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-display text-2xl font-normal">Cleaned text</h2>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={copyText}
                  disabled={!hasText}
                  className="rounded-full border border-line px-4 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Copy cleaned text
                </button>
                <button
                  type="button"
                  onClick={downloadText}
                  disabled={!hasText}
                  className="rounded-full border border-line px-4 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Download Markdown
                </button>
                {notice ? (
                  <span role="status" className="text-sm text-muted">
                    {notice}
                  </span>
                ) : null}
              </div>
            </div>
            <pre className="min-h-28 overflow-auto rounded-2xl border border-line bg-background p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
              {hasText ? cleaned : "No text was found in this image."}
            </pre>
          </div>
        </section>
      ) : null}

      <footer className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line pt-16 text-xs text-muted">
        <p>JPEG or PNG, up to 10 MB, one image at a time.</p>
        <p>SAM 3.1 marks the regions. Muse Spark reads the words.</p>
      </footer>
    </main>
  );
}
