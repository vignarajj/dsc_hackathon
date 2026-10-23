"use client";

import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";

import { cleanedMarkdownName, markdownForCleanedText, overlayPngName } from "@/lib/cleaned-text";
import {
  CancelledError,
  HIDEABLE_REGIONS,
  REGION_CONCEPTS,
  conceptsField,
  processImage,
  type ProcessResponse,
  redactField,
  type RedactStyle,
  regionCounts,
  validateImageFile,
} from "@/lib/process-client";
import { textChanges, type TextChange } from "@/lib/text-diff";

import { ShareSafe } from "./share-safe";

type Status = "idle" | "loading" | "done" | "error";
type RegionId = (typeof REGION_CONCEPTS)[number];
type HideableId = (typeof HIDEABLE_REGIONS)[number];

const REGION_LABELS: Record<RegionId, { label: string; swatch: string }> = {
  stamp: { label: "Stamp", swatch: "#dc2626" },
  signature: { label: "Signature", swatch: "#2563eb" },
  photograph: { label: "Photograph", swatch: "#ea580c" },
  rectangle: { label: "Rectangle", swatch: "#16a34a" },
};

const STEPS = [
  "Choose a JPEG or PNG up to 10 MB. A page photo, a chat, or a phone screenshot all work.",
  "Leave on the regions you want marked and choose what the share-safe copy hides. Then press Clean screenshot. It can take up to a minute.",
  "Compare the original with the overlay. Each kind of region has its own color.",
  "Drag the slider to check the share-safe copy, then download it. Copy the cleaned or the shareable text.",
] as const;

const ALL_REGIONS: Record<RegionId, boolean> = {
  stamp: true,
  signature: true,
  photograph: true,
  rectangle: true,
};

const DEFAULT_HIDE: Record<HideableId, boolean> = {
  signature: true,
  photograph: true,
  stamp: false,
};

type Choices = {
  concepts: string[];
  redact: string;
  style: RedactStyle;
  text: boolean;
};

function choicesKey(choices: Choices): string {
  return [conceptsField(choices.concepts), choices.redact, choices.style, choices.text].join("|");
}

export function Cleaner({ apiBase }: { apiBase: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [dragging, setDragging] = useState(false);
  const [regions, setRegions] = useState<Record<RegionId, boolean>>(ALL_REGIONS);
  const [appliedConcepts, setAppliedConcepts] = useState<string | null>(null);
  const [appliedKey, setAppliedKey] = useState<string | null>(null);
  const [hide, setHide] = useState<Record<HideableId, boolean>>(DEFAULT_HIDE);
  const [style, setStyle] = useState<RedactStyle>("black");
  const [hideText, setHideText] = useState(true);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => () => inFlight.current?.abort(), []);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const selected = REGION_CONCEPTS.filter((id) => regions[id]);
  const hidden = HIDEABLE_REGIONS.filter((id) => hide[id]);
  const choices: Choices = {
    concepts: selected,
    redact: redactField(hidden, selected),
    style,
    text: hideText,
  };
  const selectionChanged = result !== null && appliedKey !== choicesKey(choices);

  function chooseFile(next: File | null) {
    setResult(null);
    setNotice(null);
    setAppliedConcepts(null);
    setAppliedKey(null);
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

  function toggleRegion(id: RegionId) {
    setRegions((current) => ({ ...current, [id]: !current[id] }));
  }

  async function runClean() {
    if (!file || inFlight.current) {
      return;
    }
    const sent = choices;
    const controller = new AbortController();
    inFlight.current = controller;
    setStatus("loading");
    setError(null);
    setNotice(null);
    setResult(null);
    try {
      const processed = await processImage(file, apiBase, {
        concepts: sent.concepts,
        redact: sent.redact.split(",").filter(Boolean),
        redactStyle: sent.style,
        redactText: sent.text,
        signal: controller.signal,
      });
      setResult(processed);
      setAppliedConcepts(conceptsField(sent.concepts));
      setAppliedKey(choicesKey(sent));
      setStatus("done");
    } catch (caught) {
      if (caught instanceof CancelledError) {
        setStatus("idle");
        return;
      }
      setStatus("error");
      setError(caught instanceof Error ? caught.message : "The model request failed");
    } finally {
      inFlight.current = null;
    }
  }

  function cancelClean() {
    // The page stops waiting. A model call already under way still finishes on the server.
    inFlight.current?.abort();
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runClean();
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

  function downloadOverlay() {
    if (!result || !file) {
      return;
    }
    const anchor = document.createElement("a");
    anchor.href = `data:image/png;base64,${result.overlay_png_base64}`;
    anchor.download = overlayPngName(file.name);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  const applied = appliedConcepts ? appliedConcepts.split(",").filter(Boolean) : [];
  const counts = result ? regionCounts(result.boxes, applied) : [];

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 py-8 sm:px-8 sm:py-12">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-5">
        <p className="text-[11px] font-medium tracking-[0.22em] text-muted uppercase">
          Document screenshot cleaner
        </p>
        <p className="text-xs text-muted">Built with SAM 3.1 and Muse</p>
      </header>

      <div className="mt-10 grid items-end gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="flex flex-col gap-5">
          <h1 className="font-display max-w-xl text-5xl leading-[0.95] font-normal tracking-tight text-balance sm:text-6xl">
            A messy page, read cleanly.
          </h1>
          <p className="max-w-md text-[15px] leading-relaxed text-muted">
            Upload one JPEG or PNG. Choose which regions SAM 3.1 marks. Muse transcribes the
            page, proofreads the text, and the page shows what changed.
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

        <fieldset disabled={status === "loading"} className="flex flex-col gap-3">
          <legend className="text-sm font-medium">Regions to mark</legend>
          <div className="flex flex-wrap gap-2">
            {REGION_CONCEPTS.map((id) => (
              <label
                key={id}
                className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 text-sm has-disabled:opacity-50"
              >
                <input
                  type="checkbox"
                  value={id}
                  checked={regions[id]}
                  onChange={() => toggleRegion(id)}
                  className="accent-stamp"
                />
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: REGION_LABELS[id].swatch }}
                  aria-hidden="true"
                />
                {REGION_LABELS[id].label}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset disabled={status === "loading"} className="flex flex-col gap-3">
          <legend className="text-sm font-medium">Share-safe copy</legend>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted">Hide</span>
            {HIDEABLE_REGIONS.map((id) => (
              <label
                key={id}
                className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 text-sm has-disabled:opacity-50"
              >
                <input
                  type="checkbox"
                  checked={hide[id] && regions[id]}
                  disabled={!regions[id]}
                  onChange={() => setHide((current) => ({ ...current, [id]: !current[id] }))}
                  className="accent-stamp"
                />
                {REGION_LABELS[id].label}
              </label>
            ))}
            <span className="ml-2 text-sm text-muted" id="style-label">
              as
            </span>
            <div role="radiogroup" aria-labelledby="style-label" className="flex gap-2">
              {(["black", "blur"] as const).map((option) => (
                <label
                  key={option}
                  className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 text-sm"
                >
                  <input
                    type="radio"
                    name="redact-style"
                    value={option}
                    checked={style === option}
                    onChange={() => setStyle(option)}
                    className="accent-stamp"
                  />
                  {option === "black" ? "Black box" : "Blur"}
                </label>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={hideText}
              onChange={() => setHideText((current) => !current)}
              className="accent-stamp"
            />
            Also hide phone numbers, emails, names, and ID numbers in the text
          </label>
          <p className="text-xs text-muted">
            Only marked regions can be hidden. Black is safer than blur.
          </p>
        </fieldset>
        {selectionChanged ? (
          <p role="status" className="text-sm text-muted">
            Clean again to apply these choices.
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={!file || status === "loading"}
            className="rounded-full border border-stamp bg-stamp px-5 py-2.5 text-sm font-medium text-stamp-ink disabled:cursor-not-allowed disabled:border-line disabled:bg-transparent disabled:text-muted"
          >
            {status === "loading" ? "Cleaning…" : "Clean screenshot"}
          </button>
          {status === "loading" ? (
            <button
              type="button"
              onClick={cancelClean}
              className="rounded-full border border-line px-5 py-2.5 text-sm font-medium"
            >
              Cancel
            </button>
          ) : null}
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
        <div className="mt-6 flex flex-wrap items-center gap-3 rounded-2xl border border-stamp/40 bg-paper px-4 py-3">
          <p role="alert" className="text-sm text-stamp">
            {error}
          </p>
          {status === "error" && file ? (
            <button
              type="button"
              onClick={() => void runClean()}
              className="rounded-full border border-stamp px-4 py-1.5 text-sm font-medium text-stamp"
            >
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      {status === "done" && result && previewUrl ? (
        <section className="mt-10 flex flex-col gap-6">
          {result.warnings.length > 0 ? (
            <ul
              aria-label="Notes about this result"
              className="flex flex-col gap-1 rounded-2xl border border-line bg-paper px-4 py-3 text-sm text-muted"
            >
              {result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : null}
          <div className="grid items-start gap-4 md:grid-cols-2">
            <figure className="flex flex-col gap-3 rounded-3xl border border-line bg-paper p-4">
              <figcaption className="flex min-h-7 items-center text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
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
              <figcaption className="flex min-h-7 items-center justify-between gap-3">
                <span className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
                  SAM overlay
                </span>
                <button
                  type="button"
                  onClick={downloadOverlay}
                  className="rounded-full border border-line px-3 py-1 text-xs"
                >
                  Download PNG
                </button>
              </figcaption>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${result.overlay_png_base64}`}
                alt="Upload with SAM masks"
                className="max-h-[32rem] w-full rounded-2xl bg-background object-contain"
              />
            </figure>
          </div>
          {counts.length > 0 ? (
            <ul className="flex flex-wrap gap-2" aria-label="Regions found">
              {counts.map(({ label, count, bestScore }) => {
                const known = REGION_LABELS[label as RegionId];
                return (
                  <li
                    key={label}
                    className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1 text-sm text-muted"
                  >
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: known.swatch }}
                      aria-hidden="true"
                    />
                    <span className="text-foreground">{known.label}</span>
                    <span>
                      {count === 0 ? "none found" : `${count} found`}
                      {bestScore !== null ? ` · best ${Math.round(bestScore * 100)}%` : ""}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-sm text-muted">No regions were requested, so the overlay has no masks.</p>
          )}
          {file ? (
            <ShareSafe result={result} fileName={file.name} originalUrl={previewUrl} />
          ) : null}
          <Reading result={result} file={file} notice={notice} onCopy={copyText} onDownload={downloadText} />
          {result.models ? (
            <p className="text-xs text-muted">
              Segmented with {result.models.segmentation}. Transcribed with{" "}
              {result.models.transcription}. Proofread with {result.models.proofread}.
              {result.models.signatures
                ? ` Signatures located with ${result.models.signatures}.`
                : ""}
            </p>
          ) : null}
        </section>
      ) : null}

      <footer className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line pt-16 text-xs text-muted">
        <p>JPEG or PNG, up to 10 MB, one image at a time.</p>
        <p>SAM 3.1 marks the regions. Muse reads the words.</p>
      </footer>
    </main>
  );
}

function Reading({
  result,
  file,
  notice,
  onCopy,
  onDownload,
}: {
  result: ProcessResponse;
  file: File | null;
  notice: string | null;
  onCopy: () => void;
  onDownload: () => void;
}) {
  const cleaned = result.cleaned_text;
  const hasText = cleaned.trim().length > 0;
  const unchanged = result.original_text === result.cleaned_text;
  const changes = unchanged ? [] : textChanges(result.original_text, result.cleaned_text);

  return (
    <div className="flex flex-col gap-4 rounded-3xl border border-line bg-paper p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl font-normal">Cleaned text</h2>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onCopy}
            disabled={!hasText}
            className="rounded-full border border-line px-4 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
          >
            Copy cleaned text
          </button>
          <button
            type="button"
            onClick={onDownload}
            disabled={!hasText || !file}
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
      {unchanged ? (
        <div className="flex flex-col gap-3">
          {hasText ? <p className="text-sm text-muted">No wording changes.</p> : null}
          <pre className="min-h-28 overflow-auto rounded-2xl border border-line bg-background p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
            {hasText ? cleaned : "No text was found in this image."}
          </pre>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            Struck-through words were in the transcription. Underlined words are the proofread
            wording.
          </p>
          <div className="grid items-start gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <h3 className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
                Transcription
              </h3>
              <pre className="min-h-28 overflow-auto rounded-2xl border border-line bg-background p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
                <ChangeSpans changes={changes} show={TRANSCRIPTION} />
              </pre>
            </div>
            <div className="flex flex-col gap-2">
              <h3 className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
                Proofread
              </h3>
              <pre className="min-h-28 overflow-auto rounded-2xl border border-line bg-background p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
                {hasText ? (
                  <ChangeSpans changes={changes} show={PROOFREAD} />
                ) : (
                  "No text was found in this image."
                )}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const TRANSCRIPTION = new Set<TextChange["type"]>(["same", "removed"]);
const PROOFREAD = new Set<TextChange["type"]>(["same", "added"]);

function ChangeSpans({
  changes,
  show,
}: {
  changes: TextChange[];
  show: ReadonlySet<TextChange["type"]>;
}) {
  return changes.map((change, index) => {
    if (!show.has(change.type)) {
      return null;
    }
    if (change.type === "removed") {
      return (
        <del key={index} className="line-through decoration-stamp decoration-2">
          {change.text}
        </del>
      );
    }
    if (change.type === "added") {
      return (
        <ins key={index} className="underline decoration-foreground decoration-2 underline-offset-2">
          {change.text}
        </ins>
      );
    }
    return <span key={index}>{change.text}</span>;
  });
}
