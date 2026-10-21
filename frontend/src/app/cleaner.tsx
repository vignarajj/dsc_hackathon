"use client";

import { useEffect, useState, type FormEvent } from "react";

import { cleanedMarkdownName, markdownForCleanedText } from "@/lib/cleaned-text";
import { processImage, type ProcessResponse, validateImageFile } from "@/lib/process-client";

type Status = "idle" | "loading" | "done" | "error";

const MASK_LEGEND = [
  { label: "Stamp", swatch: "#dc2626" },
  { label: "Signature", swatch: "#2563eb" },
  { label: "Photograph", swatch: "#ea580c" },
  { label: "Rectangle", swatch: "#16a34a" },
] as const;

export function Cleaner({ apiBase }: { apiBase: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessResponse | null>(null);

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
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-3">
        <p className="text-sm font-medium text-zinc-500">SAM 3.1 and Muse Spark</p>
        <h1 className="text-3xl font-semibold tracking-tight">Document screenshot cleaner</h1>
        <p className="max-w-2xl text-zinc-600 dark:text-zinc-400">
          Upload one JPEG or PNG. SAM 3.1 marks stamps, signatures, photos, and rectangles.
          Muse Spark transcribes the page and proofreads the text.
        </p>
      </header>

      <section aria-labelledby="how-to" className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 id="how-to" className="text-sm font-medium">
          How to use it
        </h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-zinc-600 dark:text-zinc-400">
          <li>Choose a JPEG or PNG up to 10 MB. A page photo, a chat, or a phone screenshot all work.</li>
          <li>Press Clean screenshot. Reading the image can take up to a minute.</li>
          <li>Compare the original with the overlay. Each kind of region has its own color.</li>
          <li>Copy the cleaned text, or download it as Markdown.</li>
        </ol>
      </section>

      <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-busy={status === "loading"}>
        <label className="flex flex-col gap-2 text-sm font-medium">
          Screenshot
          <input
            type="file"
            name="image"
            accept="image/png,image/jpeg"
            disabled={status === "loading"}
            onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
            className="block w-full text-sm file:mr-4 file:rounded-full file:border-0 file:bg-zinc-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-zinc-700 dark:file:bg-zinc-100 dark:file:text-zinc-900"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={!file || status === "loading"}
            className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
          >
            {status === "loading" ? "Cleaning…" : "Clean screenshot"}
          </button>
          {file ? <span className="text-sm text-zinc-500">{file.name}</span> : null}
        </div>
      </form>

      {status === "loading" ? (
        <p role="status" className="text-sm text-zinc-600 dark:text-zinc-400">
          Reading the image. This can take up to a minute.
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </p>
      ) : null}

      {status === "done" && result && previewUrl ? (
        <section className="flex flex-col gap-6">
          <div className="grid items-start gap-4 md:grid-cols-2">
            <figure className="flex flex-col gap-2 rounded-2xl border border-zinc-200 p-3 dark:border-zinc-800">
              <figcaption className="text-sm font-medium">Original</figcaption>
              {/* The file is a local object URL, so the image optimizer cannot fetch it. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Original upload"
                className="max-h-[32rem] w-full rounded-lg bg-white object-contain dark:bg-zinc-950"
              />
            </figure>
            <figure className="flex flex-col gap-2 rounded-2xl border border-zinc-200 p-3 dark:border-zinc-800">
              <figcaption className="text-sm font-medium">SAM overlay</figcaption>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${result.overlay_png_base64}`}
                alt="Upload with SAM masks"
                className="max-h-[32rem] w-full rounded-lg bg-white object-contain dark:bg-zinc-950"
              />
            </figure>
          </div>
          <ul className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-zinc-600 dark:text-zinc-400">
            {MASK_LEGEND.map((item) => (
              <li key={item.label} className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-sm"
                  style={{ backgroundColor: item.swatch }}
                  aria-hidden="true"
                />
                {item.label}
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-3 rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-medium">Cleaned text</h2>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={copyText}
                  disabled={!hasText}
                  className="rounded-full border border-zinc-300 px-4 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700"
                >
                  Copy cleaned text
                </button>
                <button
                  type="button"
                  onClick={downloadText}
                  disabled={!hasText}
                  className="rounded-full border border-zinc-300 px-4 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700"
                >
                  Download Markdown
                </button>
                {notice ? (
                  <span role="status" className="text-sm text-zinc-500">
                    {notice}
                  </span>
                ) : null}
              </div>
            </div>
            <pre className="min-h-24 overflow-auto whitespace-pre-wrap rounded-lg border border-zinc-200 bg-zinc-50 p-4 font-mono text-sm dark:border-zinc-800 dark:bg-zinc-950">
              {hasText ? cleaned : "No text was found in this image."}
            </pre>
          </div>
        </section>
      ) : null}
    </main>
  );
}
