"use client";

import { useEffect, useState, type FormEvent } from "react";

import { processImage, type ProcessResponse, validateImageFile } from "@/lib/process-client";

type Status = "idle" | "loading" | "done" | "error";

export function Cleaner({ apiBase }: { apiBase: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
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

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-10 sm:px-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Document screenshot cleaner</h1>
        <p className="max-w-2xl text-zinc-600 dark:text-zinc-400">
          Upload a JPEG or PNG. SAM marks stamps, signatures, photos, and rectangles. Muse
          transcribes the page and proofreads the text.
        </p>
      </header>

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
          <div className="grid gap-4 md:grid-cols-2">
            <figure className="flex flex-col gap-2">
              <figcaption className="text-sm font-medium">Original</figcaption>
              {/* The file is a local object URL, so the image optimizer cannot fetch it. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="Original upload"
                className="w-full rounded-lg border border-zinc-200 bg-white dark:border-zinc-800"
              />
            </figure>
            <figure className="flex flex-col gap-2">
              <figcaption className="text-sm font-medium">SAM overlay</figcaption>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${result.overlay_png_base64}`}
                alt="Upload with SAM masks"
                className="w-full rounded-lg border border-zinc-200 bg-white dark:border-zinc-800"
              />
            </figure>
          </div>
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-medium">Cleaned text</h2>
            <pre className="min-h-24 overflow-auto whitespace-pre-wrap rounded-lg border border-zinc-200 bg-zinc-50 p-4 font-mono text-sm dark:border-zinc-800 dark:bg-zinc-950">
              {result.cleaned_text.trim() ? result.cleaned_text : "No text was found in this image."}
            </pre>
          </div>
        </section>
      ) : null}
    </main>
  );
}
