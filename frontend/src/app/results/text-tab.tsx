"use client";

import { useState } from "react";

import { cleanedMarkdownName, markdownForCleanedText } from "@/lib/cleaned-text";
import type { ProcessResponse } from "@/lib/process-client";
import { textChanges, type TextChange } from "@/lib/text-diff";

import { AskBox } from "./ask-box";

export function TextTab({
  result,
  fileName,
  apiBase,
}: {
  result: ProcessResponse;
  fileName: string;
  apiBase: string;
}) {
  const [notice, setNotice] = useState<string | null>(null);
  const cleaned = result.cleaned_text;
  const hasText = cleaned.trim().length > 0;

  async function copyText() {
    if (!hasText) {
      return;
    }
    try {
      await navigator.clipboard.writeText(cleaned);
      setNotice("Copied");
    } catch {
      setNotice("Could not copy the text. Select it and copy it manually.");
    }
  }

  function downloadText() {
    if (!hasText) {
      return;
    }
    const blob = new Blob([markdownForCleanedText(cleaned)], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = cleanedMarkdownName(fileName);
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-4 rounded-3xl border border-line bg-paper p-5">
      <Reading result={result} notice={notice} onCopy={copyText} onDownload={downloadText} />
      <AskBox
        apiBase={apiBase}
        text={result.cleaned_text.trim() ? result.cleaned_text : result.original_text}
        document={result.document}
      />
    </div>
  );
}

function Reading({
  result,
  notice,
  onCopy,
  onDownload,
}: {
  result: ProcessResponse;
  notice: string | null;
  onCopy: () => void;
  onDownload: () => void;
}) {
  const cleaned = result.cleaned_text;
  const hasText = cleaned.trim().length > 0;
  const unchanged = result.original_text === result.cleaned_text;
  const changes = unchanged ? [] : textChanges(result.original_text, result.cleaned_text);

  return (
    <div className="flex flex-col gap-4">
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
