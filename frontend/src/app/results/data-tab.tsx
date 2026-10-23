"use client";

import { useState } from "react";

import { dataCsvName, dataJsonName } from "@/lib/cleaned-text";
import { dataJson, documentTypeLabel, fieldsCsv } from "@/lib/exports";
import type { ProcessResponse } from "@/lib/process-client";

import { EmptyTab } from "./empty-tab";

export function DataTab({
  result,
  fileName,
  requested,
}: {
  result: ProcessResponse;
  fileName: string;
  requested: boolean;
}) {
  const [notice, setNotice] = useState<string | null>(null);
  const document = result.document;
  if (!document) {
    return (
      <EmptyTab title="Document data">
        {!requested
          ? "Data was not requested. Tick “Pull out the document type and key fields”, then clean again."
          : result.original_text.trim()
            ? "The fields could not be read this time. The note above says why. Clean again to retry."
            : "No text was found in this image, so there are no fields to show."}
      </EmptyTab>
    );
  }
  const ungrounded = document.fields.filter((field) => !field.found_in_text).length;

  function save(contents: string, type: string, name: string) {
    const url = URL.createObjectURL(new Blob([contents], { type }));
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice("Copied");
    } catch {
      setNotice("Could not copy. Select the value and copy it manually.");
    }
  }

  return (
    <section
      aria-labelledby="document-data"
      className="flex flex-col gap-4 rounded-3xl border border-line bg-paper p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="document-data" className="font-display text-2xl font-normal">
            Document data
          </h2>
          <span className="rounded-full border border-stamp/40 px-3 py-0.5 text-[11px] font-medium tracking-[0.12em] text-stamp uppercase">
            {documentTypeLabel(document.type)}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() =>
              save(dataJson(result, fileName), "application/json", dataJsonName(fileName))
            }
            className="rounded-full border border-line px-4 py-1.5 text-sm"
          >
            Download JSON
          </button>
          <button
            type="button"
            onClick={() =>
              save(fieldsCsv(document.fields), "text/csv;charset=utf-8", dataCsvName(fileName))
            }
            disabled={document.fields.length === 0}
            className="rounded-full border border-line px-4 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
          >
            Download CSV
          </button>
          {notice ? (
            <span role="status" className="text-sm text-muted">
              {notice}
            </span>
          ) : null}
        </div>
      </div>
      {document.title ? <p className="font-medium">{document.title}</p> : null}
      {document.summary ? <p className="text-sm text-muted">{document.summary}</p> : null}
      {document.fields.length > 0 ? (
        <div>
          <table className="w-full table-fixed border-collapse text-left text-sm">
            <colgroup>
              <col className="w-[34%]" />
              <col />
              <col className="w-16" />
            </colgroup>
            <thead>
              <tr className="border-b border-line text-[11px] tracking-[0.18em] text-muted uppercase">
                <th scope="col" className="py-2 pr-4 font-medium">
                  Field
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  Value
                </th>
                <th scope="col" className="py-2 font-medium">
                  <span className="sr-only">Copy</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {document.fields.map((field, index) => (
                <tr key={`${field.label}-${index}`} className="border-b border-line/60 align-top">
                  <th scope="row" className="py-2 pr-3 font-normal break-words text-muted">
                    {field.label}
                  </th>
                  <td className="py-2 pr-3 break-words">
                    {field.value}
                    {field.found_in_text ? null : (
                      <span className="ml-2 rounded-full border border-stamp/40 px-2 py-0.5 text-[11px] whitespace-nowrap text-stamp">
                        not found in text
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    <button
                      type="button"
                      onClick={() => void copy(field.value)}
                      aria-label={`Copy ${field.label}`}
                      className="rounded-full border border-line px-3 py-0.5 text-xs"
                    >
                      Copy
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted">No key fields were found in this document.</p>
      )}
      {ungrounded > 0 ? (
        <p className="text-xs text-muted">
          Values marked &quot;not found in text&quot; do not appear in the transcription or the
          proofread. Check them before you rely on them.
        </p>
      ) : null}
    </section>
  );
}
