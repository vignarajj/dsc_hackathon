import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { loadSample, sampleThumbUrl, sampleUrl } from "./samples.ts";

describe("samples", () => {
  it("point at the public folder", () => {
    assert.equal(sampleUrl("invoice"), "/samples/invoice.jpg");
    assert.equal(sampleThumbUrl("chat"), "/samples/thumbs/chat.jpg");
  });

  it("load as a JPEG file named after the sample", async () => {
    const file = await loadSample("signed-form", async (input) => {
      assert.equal(input, "/samples/signed-form.jpg");
      return new Response(new Uint8Array([0xff, 0xd8, 0xff]), { status: 200 });
    });
    assert.equal(file.name, "signed-form.jpg");
    assert.equal(file.type, "image/jpeg");
    assert.equal(file.size, 3);
  });

  it("explain a failed load", async () => {
    await assert.rejects(
      loadSample("chat", async () => new Response(null, { status: 404 })),
      /Could not load the sample/,
    );
  });
});
