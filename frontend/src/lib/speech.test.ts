import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { speechChunks } from "./speech.ts";

describe("speechChunks", () => {
  it("splits at sentence ends and joins lines", () => {
    assert.deepEqual(speechChunks("Hi Sam,\nThe plumber comes at 10. Pay him $85! Thanks?"), [
      "Hi Sam, The plumber comes at 10.",
      "Pay him $85!",
      "Thanks?",
    ]);
  });

  it("cuts a long sentence at a comma or space, never past the limit", () => {
    const sentence = `${"word ".repeat(30)}, ${"more ".repeat(30)}end.`;
    const chunks = speechChunks(sentence, 80);
    assert.ok(chunks.length > 2);
    assert.ok(chunks.every((chunk) => chunk.length <= 80));
    assert.equal(chunks.join(" ").replace(/\s+/g, " "), sentence.replace(/\s+/g, " ").trim());
  });

  it("cuts a long unbroken run at the limit", () => {
    assert.deepEqual(speechChunks("x".repeat(25), 10), ["x".repeat(10), "x".repeat(10), "x".repeat(5)]);
  });

  it("returns nothing for blank text", () => {
    assert.deepEqual(speechChunks("  \n "), []);
  });
});
