import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  parseProcessResponse,
  processImage,
  readErrorDetail,
  validateImageFile,
} from "./process-client.ts";

const overlay = "iVBORw0KGgo=";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("validateImageFile", () => {
  it("accepts a png and a jpeg", () => {
    assert.equal(validateImageFile({ type: "image/png", size: 12 }), null);
    assert.equal(validateImageFile({ type: "image/jpeg", size: 12 }), null);
  });

  it("rejects the wrong type, an empty file, and a file over 10 MB", () => {
    assert.equal(
      validateImageFile({ type: "image/gif", size: 12 }),
      "Only JPEG and PNG images are accepted",
    );
    assert.equal(validateImageFile({ type: "image/png", size: 0 }), "Image file is empty");
    assert.match(validateImageFile({ type: "image/png", size: 10 * 1024 * 1024 + 1 }) ?? "", /10 MB/);
  });
});

describe("readErrorDetail", () => {
  it("prefers the backend detail for 413 and 502", () => {
    assert.equal(
      readErrorDetail(413, { detail: "Image exceeds the 10 MB limit" }),
      "Image exceeds the 10 MB limit",
    );
    assert.equal(
      readErrorDetail(502, { detail: "The model request timed out" }),
      "The model request timed out",
    );
  });

  it("falls back when the body has no detail", () => {
    assert.equal(readErrorDetail(502, null), "The model request failed");
    assert.equal(readErrorDetail(500, { detail: "" }), "Request failed (500)");
  });
});

describe("processImage", () => {
  it("returns the contract fields from a successful response", async () => {
    const file = new File([new Uint8Array([1, 2, 3])], "note.png", { type: "image/png" });
    const result = await processImage(file, "http://127.0.0.1:8000/", async (input, init) => {
      assert.equal(input, "http://127.0.0.1:8000/api/process");
      assert.equal(init?.method, "POST");
      assert.ok(init?.body instanceof FormData);
      return jsonResponse(200, {
        boxes: [{ x: 1, y: 2, w: 3, h: 4, label: "stamp", score: 0.5 }],
        overlay_png_base64: overlay,
        original_text: "Reciept",
        cleaned_text: "Receipt",
      });
    });
    assert.equal(result.cleaned_text, "Receipt");
    assert.equal(result.boxes[0]?.label, "stamp");
    assert.equal(parseProcessResponse(result).overlay_png_base64, overlay);
  });

  it("surfaces a 502 detail and a network failure", async () => {
    const file = new File([new Uint8Array([1])], "note.png", { type: "image/png" });
    await assert.rejects(
      processImage(file, "http://127.0.0.1:8000", async () =>
        jsonResponse(502, { detail: "The model request timed out" }),
      ),
      /timed out/,
    );
    await assert.rejects(
      processImage(file, "http://127.0.0.1:8000", async () => {
        throw new Error("offline");
      }),
      /Could not reach the cleaner/,
    );
  });

  it("rejects an invalid file before calling the API", async () => {
    let called = false;
    const file = new File([new Uint8Array([1])], "note.gif", { type: "image/gif" });
    await assert.rejects(
      processImage(file, "http://127.0.0.1:8000", async () => {
        called = true;
        return jsonResponse(200, {});
      }),
      /Only JPEG and PNG/,
    );
    assert.equal(called, false);
  });
});
