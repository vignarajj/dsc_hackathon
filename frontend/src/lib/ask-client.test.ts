import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { askDocument, questionProblem, suggestedQuestions } from "./ask-client.ts";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("suggestedQuestions", () => {
  it("fits the document type and falls back to general questions", () => {
    assert.equal(suggestedQuestions("invoice")[0], "What is the total due?");
    assert.equal(suggestedQuestions("other")[0], "What is this document about?");
    assert.equal(suggestedQuestions(null).length, 3);
  });
});

describe("questionProblem", () => {
  it("mirrors the API limits", () => {
    assert.equal(questionProblem("  "), "Type a question.");
    assert.match(questionProblem("x".repeat(301)) ?? "", /under 300/);
    assert.equal(questionProblem("Who signed?"), null);
  });
});

describe("askDocument", () => {
  it("posts the question, text, and fields as JSON", async () => {
    let sent: Record<string, unknown> = {};
    const answer = await askDocument(
      "http://127.0.0.1:8000/",
      {
        question: "What is the total due?",
        text: "Total due: $1,200.00",
        fields: [{ label: "Total due", value: "$1,200.00", found_in_text: true }],
      },
      {
        fetchImpl: async (input, init) => {
          assert.equal(input, "http://127.0.0.1:8000/api/ask");
          assert.equal(new Headers(init?.headers).get("content-type"), "application/json");
          sent = JSON.parse(String(init?.body));
          return json(200, { answer: "$1,200.00.", quote: "Total due: $1,200.00" });
        },
      },
    );
    assert.deepEqual(sent.fields, [{ label: "Total due", value: "$1,200.00" }]);
    assert.deepEqual(answer, { answer: "$1,200.00.", quote: "Total due: $1,200.00" });
  });

  it("caps very long text and shows the API's error", async () => {
    let length = 0;
    await assert.rejects(
      askDocument(
        "http://x",
        { question: "Why?", text: "a".repeat(25_000) },
        {
          fetchImpl: async (_input, init) => {
            length = (JSON.parse(String(init?.body)) as { text: string }).text.length;
            return json(429, { detail: "Too many requests. Wait a minute and try again." });
          },
        },
      ),
      /Too many requests/,
    );
    assert.equal(length, 20_000);
  });

  it("rejects an empty question without calling the API", async () => {
    let called = false;
    await assert.rejects(
      askDocument("http://x", { question: " ", text: "t" }, {
        fetchImpl: async () => {
          called = true;
          return json(200, {});
        },
      }),
      /Type a question/,
    );
    assert.equal(called, false);
  });

  it("explains a timeout, a lost server, and a strange reply", async () => {
    const hang: typeof fetch = (_input, init) =>
      new Promise((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("x"))));
    await assert.rejects(askDocument("http://x", { question: "Why?", text: "t" }, { fetchImpl: hang, timeoutMs: 10 }), /took too long/);
    await assert.rejects(
      askDocument("http://x", { question: "Why?", text: "t" }, { fetchImpl: async () => { throw new Error("down"); } }),
      /Could not reach/,
    );
    await assert.rejects(
      askDocument("http://x", { question: "Why?", text: "t" }, { fetchImpl: async () => json(200, { quote: "x" }) }),
      /unexpected answer/,
    );
  });
});
