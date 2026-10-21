import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { textChanges } from "./text-diff.ts";

describe("textChanges", () => {
  it("returns one piece when nothing changed", () => {
    assert.deepEqual(textChanges("Call the landlord", "Call the landlord"), [
      { type: "same", text: "Call the landlord" },
    ]);
    assert.deepEqual(textChanges("", ""), []);
  });

  it("marks a capitalization change and keeps the shared words", () => {
    const changes = textChanges("call the landlord", "Call the landlord");
    assert.deepEqual(
      changes.filter((change) => change.type !== "same").map((change) => change.text),
      ["call", "Call"],
    );
    assert.equal(
      changes
        .filter((change) => change.type === "same")
        .map((change) => change.text)
        .join(""),
      " the landlord",
    );
  });

  it("keeps a line break attached to the surrounding words", () => {
    const changes = textChanges("Rent is due\nFriday", "Rent is due Friday");
    const removed = changes.find((change) => change.type === "removed");
    const added = changes.find((change) => change.type === "added");
    assert.equal(removed?.text.includes("\n"), true);
    assert.equal(added?.text, " ");
  });

  it("rebuilds each side from the shared and changed pieces", () => {
    const before = "call the landlord about the leak";
    const after = "Call the landlord about the leak";
    const changes = textChanges(before, after);
    const join = (types: Array<"same" | "removed" | "added">) =>
      changes
        .filter((change) => types.includes(change.type))
        .map((change) => change.text)
        .join("");
    assert.equal(join(["same", "removed"]), before);
    assert.equal(join(["same", "added"]), after);
  });

  it("collapses a very long change into one removed block and one added block", () => {
    const before = `${"a ".repeat(751)}tail`;
    const after = `${"b ".repeat(751)}tail`;
    const changes = textChanges(before, after);
    assert.deepEqual(
      changes.map((change) => change.type),
      ["removed", "added"],
    );
    assert.equal(changes[0]?.text, before);
    assert.equal(changes[1]?.text, after);
  });
});
