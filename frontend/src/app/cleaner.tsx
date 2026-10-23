"use client";

import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";

import {
  CUSTOM_SUGGESTIONS,
  CancelledError,
  HIDEABLE_REGIONS,
  MAX_CUSTOM,
  REGION_CONCEPTS,
  conceptsField,
  customChoice,
  processImage,
  type ProcessResponse,
  redactField,
  type RedactStyle,
  type StageState,
  validateImageFile,
} from "@/lib/process-client";
import { SAMPLES, type SampleId, loadSample, sampleThumbUrl } from "@/lib/samples";

import { ProgressList } from "./progress-list";
import { DataTab } from "./results/data-tab";
import { type RegionId, REGION_LABELS, regionLabel, swatchFor } from "./results/labels";
import { Overview } from "./results/overview";
import { ResultTabs } from "./results/result-tabs";
import { ShareTab } from "./results/share-tab";
import { TextTab } from "./results/text-tab";

type Status = "idle" | "loading" | "done" | "error";

const STEPS = [
  "Choose a JPEG or PNG up to 10 MB, or try one of the samples. A page photo, a chat, or a phone screenshot all work.",
  "Leave on the regions you want marked and choose what the share-safe copy hides. Then press Clean screenshot. It can take up to a minute.",
  "Drag the slider to compare the original with the overlay. Point at a region to outline it.",
  "Use the tabs for the text, the document data, and the share-safe copy to download or copy.",
] as const;

const ALL_REGIONS: Record<RegionId, boolean> = {
  stamp: true,
  signature: true,
  photograph: true,
  rectangle: true,
};

const DEFAULT_HIDE: Record<string, boolean> = {
  signature: true,
  photograph: true,
  stamp: false,
};

type Choices = {
  concepts: string[];
  custom: string[];
  redact: string;
  style: RedactStyle;
  text: boolean;
  extract: boolean;
  describe: boolean;
};

function choicesKey(choices: Choices): string {
  return [
    conceptsField(choices.concepts),
    choices.custom.join(","),
    choices.redact,
    choices.style,
    choices.text,
    choices.extract,
    choices.describe,
  ].join("|");
}


export function Cleaner({ apiBase }: { apiBase: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [loadingSample, setLoadingSample] = useState<SampleId | null>(null);
  const [runs, setRuns] = useState(0);
  const [appliedExtract, setAppliedExtract] = useState(false);
  const [stages, setStages] = useState<StageState[]>([]);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [dragging, setDragging] = useState(false);
  const [regions, setRegions] = useState<Record<RegionId, boolean>>(ALL_REGIONS);
  const [appliedConcepts, setAppliedConcepts] = useState<string | null>(null);
  const [appliedKey, setAppliedKey] = useState<string | null>(null);
  const [hide, setHide] = useState<Record<string, boolean>>(DEFAULT_HIDE);
  const [custom, setCustom] = useState<string[]>([]);
  const [customDraft, setCustomDraft] = useState("");
  const [customError, setCustomError] = useState<string | null>(null);
  const [style, setStyle] = useState<RedactStyle>("black");
  const [hideText, setHideText] = useState(true);
  const [extract, setExtract] = useState(true);
  const [describe, setDescribe] = useState(false);
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
  const hideable = [...HIDEABLE_REGIONS, ...custom];
  const hidden = hideable.filter((id) => hide[id]);
  const choices: Choices = {
    concepts: selected,
    custom,
    redact: redactField(hidden, selected, custom),
    style,
    text: hideText,
    extract,
    describe,
  };
  const selectionChanged = result !== null && appliedKey !== choicesKey(choices);

  function chooseFile(next: File | null) {
    setResult(null);
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

  function addCustom(raw: string) {
    const choice = customChoice(raw, custom);
    if (choice.kind === "error") {
      setCustomError(choice.message);
      return;
    }
    if (choice.kind === "preset") {
      setRegions((current) => ({ ...current, [choice.name]: true }));
    } else {
      setCustom((current) => [...current, choice.name]);
    }
    setCustomDraft("");
    setCustomError(null);
  }

  function removeCustom(name: string) {
    setCustom((current) => current.filter((item) => item !== name));
    setHide((current) => ({ ...current, [name]: false }));
    setCustomError(null);
  }

  async function chooseSample(id: SampleId) {
    if (status === "loading") {
      return;
    }
    setLoadingSample(id);
    try {
      chooseFile(await loadSample(id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the sample.");
      setStatus("error");
    } finally {
      setLoadingSample(null);
    }
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
    setResult(null);
    setStages([]);
    try {
      const processed = await processImage(file, apiBase, {
        concepts: sent.concepts,
        custom: sent.custom,
        redact: sent.redact.split(",").filter(Boolean),
        redactStyle: sent.style,
        redactText: sent.text,
        extract: sent.extract,
        describe: sent.describe,
        signal: controller.signal,
        onProgress: setStages,
      });
      setResult(processed);
      setAppliedConcepts([conceptsField(sent.concepts), ...sent.custom].filter(Boolean).join(","));
      setAppliedKey(choicesKey(sent));
      setAppliedExtract(sent.extract);
      setRuns((count) => count + 1);
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

  const applied = appliedConcepts ? appliedConcepts.split(",").filter(Boolean) : [];
  const appliedCustom = applied.filter((label) => !REGION_LABELS[label as RegionId]);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 py-8 sm:px-8 sm:py-12">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-5">
        <p className="text-[11px] font-medium tracking-[0.22em] text-muted uppercase">
          Document screenshot cleaner
        </p>
        <p className="text-xs text-muted">
          SAM 3.1 finds the regions. Muse reads the page, fixes the text, and pulls out the data.
        </p>
      </header>

      <div className="mt-10 grid items-end gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <div className="flex flex-col gap-5">
          <h1 className="font-display max-w-xl text-5xl leading-[0.95] font-normal tracking-tight text-balance sm:text-6xl">
            A messy page, read cleanly.
          </h1>
          <p className="max-w-md text-[15px] leading-relaxed text-muted">
            Upload one JPEG or PNG. SAM 3.1 marks signatures, photos, stamps, or anything you
            name. Muse transcribes and proofreads the page and pulls out its key fields. One click
            gives you a copy that is safe to share.
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

        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted" id="samples-label">
            No file to hand? Try a sample.
          </p>
          <ul aria-labelledby="samples-label" className="flex flex-wrap gap-2">
            {SAMPLES.map((sample) => (
              <li key={sample.id}>
                <button
                  type="button"
                  onClick={() => void chooseSample(sample.id)}
                  disabled={status === "loading" || loadingSample !== null}
                  aria-pressed={file?.name === `${sample.id}.jpg`}
                  className="flex items-center gap-2 rounded-2xl border border-line bg-paper py-1.5 pr-3 pl-1.5 text-left text-sm aria-pressed:border-stamp disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={sampleThumbUrl(sample.id)}
                    alt=""
                    width={40}
                    height={40}
                    className="h-10 w-10 rounded-lg bg-background object-cover"
                  />
                  {loadingSample === sample.id ? "Loading…" : sample.label}
                </button>
              </li>
            ))}
          </ul>
        </div>

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
            {custom.map((name) => (
              <span
                key={name}
                className="flex items-center gap-2 rounded-full border border-line bg-paper py-1.5 pr-1.5 pl-3 text-sm"
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: swatchFor(name, undefined, custom) }}
                  aria-hidden="true"
                />
                {regionLabel(name)}
                <button
                  type="button"
                  onClick={() => removeCustom(name)}
                  aria-label={`Remove ${name}`}
                  className="rounded-full px-1.5 leading-none text-muted hover:text-foreground"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
          <div className="flex flex-col gap-2">
            <label htmlFor="custom-region" className="text-sm text-muted">
              Find something else (up to {MAX_CUSTOM})
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                id="custom-region"
                type="text"
                value={customDraft}
                maxLength={40}
                placeholder="logo"
                disabled={custom.length >= MAX_CUSTOM}
                aria-describedby={customError ? "custom-error" : undefined}
                aria-invalid={customError ? true : undefined}
                onChange={(event) => {
                  setCustomDraft(event.target.value);
                  setCustomError(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addCustom(customDraft);
                  }
                }}
                className="w-44 rounded-full border border-line bg-paper px-3 py-1.5 text-sm disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => addCustom(customDraft)}
                disabled={!customDraft.trim() || custom.length >= MAX_CUSTOM}
                className="rounded-full border border-line px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
              >
                Add
              </button>
              {CUSTOM_SUGGESTIONS.filter((name) => !custom.includes(name)).map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => addCustom(name)}
                  disabled={custom.length >= MAX_CUSTOM}
                  className="rounded-full border border-dashed border-line px-3 py-1 text-xs text-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
                >
                  + {regionLabel(name)}
                </button>
              ))}
            </div>
            {customError ? (
              <p id="custom-error" role="alert" className="text-sm text-stamp">
                {customError}
              </p>
            ) : null}
          </div>
        </fieldset>

        <fieldset disabled={status === "loading"} className="flex flex-col gap-3">
          <legend className="text-sm font-medium">Share-safe copy</legend>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted">Hide</span>
            {hideable.map((id) => {
              const marked = custom.includes(id) || regions[id as RegionId];
              return (
                <label
                  key={id}
                  className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 text-sm has-disabled:opacity-50"
                >
                  <input
                    type="checkbox"
                    checked={Boolean(hide[id]) && marked}
                    disabled={!marked}
                    onChange={() => setHide((current) => ({ ...current, [id]: !current[id] }))}
                    className="accent-stamp"
                  />
                  {regionLabel(id)}
                </label>
              );
            })}
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
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={extract}
            disabled={status === "loading"}
            onChange={() => setExtract((current) => !current)}
            className="accent-stamp"
          />
          Pull out the document type and key fields
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={describe}
            disabled={status === "loading"}
            onChange={() => setDescribe((current) => !current)}
            className="accent-stamp"
          />
          Describe each region in a few words
          <span className="text-xs text-muted">(up to 8 more Muse calls)</span>
        </label>
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
            {stages.length > 0
              ? `${stages.filter((item) => item.status === "done").length} of ${stages.length} steps done. This can take up to a minute.`
              : "Reading the image. This can take up to a minute."}
          </p>
          {stages.length > 0 ? (
            <div className="mt-3">
              <ProgressList stages={stages} />
            </div>
          ) : null}
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
          <ResultTabs
            key={runs}
            label="Result"
            tabs={[
              {
                id: "overview",
                label: "Overview",
                panel: (
                  <Overview
                    result={result}
                    fileName={file?.name ?? "screenshot"}
                    originalUrl={previewUrl}
                    labels={applied}
                    custom={appliedCustom}
                  />
                ),
              },
              {
                id: "text",
                label: "Text",
                panel: <TextTab result={result} fileName={file?.name ?? "screenshot"} />,
              },
              {
                id: "data",
                label: "Data",
                panel: (
                  <DataTab
                    result={result}
                    fileName={file?.name ?? "screenshot"}
                    requested={appliedExtract}
                  />
                ),
              },
              {
                id: "share",
                label: "Share-safe",
                panel: (
                  <ShareTab
                    result={result}
                    fileName={file?.name ?? "screenshot"}
                    originalUrl={previewUrl}
                  />
                ),
              },
            ]}
          />
        </section>
      ) : null}

      <footer className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line pt-16 text-xs text-muted">
        <p>JPEG or PNG, up to 10 MB, one image at a time. Nothing you upload is stored.</p>
        <p>SAM 3.1 marks the regions. Muse reads the words.</p>
      </footer>
    </main>
  );
}
