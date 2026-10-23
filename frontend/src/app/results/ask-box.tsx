"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  askDocument,
  type AskAnswer,
  MAX_QUESTION_CHARS,
  questionProblem,
  suggestedQuestions,
} from "@/lib/ask-client";
import type { DocumentData } from "@/lib/process-client";

type Asked = { question: string } & AskAnswer;

export function AskBox({
  apiBase,
  text,
  document,
}: {
  apiBase: string;
  text: string;
  document: DocumentData | null;
}) {
  const [question, setQuestion] = useState("");
  const [answers, setAnswers] = useState<Asked[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => () => inFlight.current?.abort(), []);

  if (!text.trim()) {
    return (
      <p className="text-sm text-muted">
        There is no text to ask about. Clean an image with words in it first.
      </p>
    );
  }

  async function ask(asked: string) {
    const problem = questionProblem(asked);
    if (problem) {
      setError(problem);
      return;
    }
    if (inFlight.current) {
      return;
    }
    const controller = new AbortController();
    inFlight.current = controller;
    setBusy(true);
    setError(null);
    try {
      const reply = await askDocument(
        apiBase,
        { question: asked, text, fields: document?.fields },
        { signal: controller.signal },
      );
      setAnswers((current) => [{ question: asked.trim(), ...reply }, ...current]);
      setQuestion("");
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : "The model request failed");
      }
    } finally {
      inFlight.current = null;
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(question);
  }

  return (
    <section aria-labelledby="ask" className="flex flex-col gap-3 border-t border-line pt-4">
      <h3 id="ask" className="text-[11px] font-medium tracking-[0.18em] text-muted uppercase">
        Ask the document
      </h3>
      <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-2">
        <label htmlFor="question" className="sr-only">
          Question about the document
        </label>
        <input
          id="question"
          type="text"
          value={question}
          maxLength={MAX_QUESTION_CHARS}
          placeholder="Ask a question about this page"
          disabled={busy}
          aria-describedby={error ? "ask-error" : undefined}
          onChange={(event) => {
            setQuestion(event.target.value);
            setError(null);
          }}
          className="min-w-0 flex-1 basis-56 rounded-full border border-line bg-background px-4 py-1.5 text-sm disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          className="rounded-full border border-line px-4 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>
      <div className="flex flex-wrap gap-2">
        {suggestedQuestions(document?.type).map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            disabled={busy}
            onClick={() => void ask(suggestion)}
            className="rounded-full border border-dashed border-line px-3 py-1 text-xs text-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
          >
            {suggestion}
          </button>
        ))}
      </div>
      {error ? (
        <p id="ask-error" role="alert" className="text-sm text-stamp">
          {error}
        </p>
      ) : null}
      {answers.length > 0 ? (
        <ol aria-label="Answers" className="flex flex-col gap-3">
          {answers.map((item, index) => (
            <li
              key={`${answers.length - index}`}
              className="flex flex-col gap-1 rounded-2xl border border-line bg-background p-3"
            >
              <p className="text-xs text-muted">{item.question}</p>
              <p className="text-sm">{item.answer}</p>
              {item.quote ? (
                <blockquote className="border-l-2 border-stamp pl-3 font-mono text-xs whitespace-pre-wrap text-muted">
                  From the page: “{item.quote}”
                </blockquote>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-xs text-muted">
          Answers come only from this page&apos;s text. A quote is shown when Muse points to the
          exact words.
        </p>
      )}
    </section>
  );
}
