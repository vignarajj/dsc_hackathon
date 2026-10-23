import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  CancelledError,
  conceptsField,
  customChoice,
  parseProcessResponse,
  processImage,
  readErrorDetail,
  redactField,
  regionCounts,
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
    assert.match(readErrorDetail(429, null), /Too many requests/);
    assert.equal(readErrorDetail(500, { detail: "" }), "Request failed (500)");
  });
});

describe("conceptsField", () => {
  it("keeps the canonical order and drops unknown names", () => {
    assert.equal(conceptsField(undefined), "stamp,signature,photograph,rectangle");
    assert.equal(conceptsField(["rectangle", "stamp", "stamp", "logo"]), "stamp,rectangle");
    assert.equal(conceptsField([]), "");
  });
});

describe("processImage", () => {
  it("returns the contract fields from a successful response", async () => {
    const file = new File([new Uint8Array([1, 2, 3])], "note.png", { type: "image/png" });
    const result = await processImage(file, "http://127.0.0.1:8000/", {
      fetchImpl: async (input, init) => {
        assert.equal(input, "http://127.0.0.1:8000/api/process");
        assert.equal(init?.method, "POST");
        assert.ok(init?.body instanceof FormData);
        assert.equal(
          (init.body as FormData).get("concepts"),
          "stamp,signature,photograph,rectangle",
        );
        return jsonResponse(200, {
          boxes: [{ x: 1, y: 2, w: 3, h: 4, label: "stamp", score: 0.5 }],
          overlay_png_base64: overlay,
          original_text: "Reciept",
          cleaned_text: "Receipt",
        });
      },
    });
    assert.equal(result.cleaned_text, "Receipt");
    assert.equal(result.boxes[0]?.label, "stamp");
    assert.equal(result.models, null);
    assert.equal(parseProcessResponse(result).overlay_png_base64, overlay);
  });

  it("sends the selected regions, including none", async () => {
    const file = new File([new Uint8Array([1])], "note.png", { type: "image/png" });
    const seen: string[] = [];
    const fetchImpl: typeof fetch = async (_input, init) => {
      assert.ok(init?.body instanceof FormData);
      seen.push(String((init.body as FormData).get("concepts")));
      return jsonResponse(200, {
        boxes: [],
        overlay_png_base64: overlay,
        original_text: "Hello",
        cleaned_text: "Hello",
      });
    };
    await processImage(file, "http://127.0.0.1:8000", { concepts: ["photograph"], fetchImpl });
    await processImage(file, "http://127.0.0.1:8000", { concepts: [], fetchImpl });
    assert.deepEqual(seen, ["photograph", ""]);
  });

  it("surfaces a 502 detail and a network failure", async () => {
    const file = new File([new Uint8Array([1])], "note.png", { type: "image/png" });
    await assert.rejects(
      processImage(file, "http://127.0.0.1:8000", {
        fetchImpl: async () => jsonResponse(502, { detail: "The model request timed out" }),
      }),
      /timed out/,
    );
    await assert.rejects(
      processImage(file, "http://127.0.0.1:8000", {
        fetchImpl: async () => {
          throw new Error("offline");
        },
      }),
      /Could not reach the cleaner/,
    );
  });

  it("rejects an invalid file before calling the API", async () => {
    let called = false;
    const file = new File([new Uint8Array([1])], "note.gif", { type: "image/gif" });
    await assert.rejects(
      processImage(file, "http://127.0.0.1:8000", {
        fetchImpl: async () => {
          called = true;
          return jsonResponse(200, {});
        },
      }),
      /Only JPEG and PNG/,
    );
    assert.equal(called, false);
  });
});

describe("parseProcessResponse models", () => {
  it("keeps the model names when the API sends them", () => {
    const parsed = parseProcessResponse({
      boxes: [],
      overlay_png_base64: overlay,
      original_text: "",
      cleaned_text: "",
      models: { segmentation: "sam-3.1", transcription: "muse-spark-1.3", proofread: "muse-wonder-1.0" },
    });
    assert.deepEqual(parsed.models, {
      segmentation: "sam-3.1",
      transcription: "muse-spark-1.3",
      proofread: "muse-wonder-1.0",
      signatures: null,
    });
  });
});

describe("regionCounts", () => {
  it("counts boxes for each requested region and keeps the best score", () => {
    const boxes = [
      { x: 0, y: 0, w: 1, h: 1, label: "stamp", score: 0.6 },
      { x: 0, y: 0, w: 1, h: 1, label: "stamp", score: 0.9 },
      { x: 0, y: 0, w: 1, h: 1, label: "signature", score: null },
    ];
    assert.deepEqual(regionCounts(boxes, ["signature", "stamp", "photograph"]), [
      { label: "stamp", count: 2, bestScore: 0.9 },
      { label: "signature", count: 1, bestScore: null },
      { label: "photograph", count: 0, bestScore: null },
    ]);
    assert.deepEqual(regionCounts(boxes, []), []);
  });
});

describe("processImage abort", () => {
  const file = new File([new Uint8Array([1])], "note.png", { type: "image/png" });
  const hang: typeof fetch = (_input, init) =>
    new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
    });

  it("gives up after the timeout", async () => {
    await assert.rejects(
      processImage(file, "http://127.0.0.1:8000", { fetchImpl: hang, timeoutMs: 10 }),
      /took too long/,
    );
  });

  it("reports a cancel as CancelledError", async () => {
    const controller = new AbortController();
    const pending = processImage(file, "http://127.0.0.1:8000", {
      fetchImpl: hang,
      signal: controller.signal,
    });
    controller.abort();
    await assert.rejects(pending, CancelledError);
  });
});

describe("share-safe request fields", () => {
  it("only hides regions that are also marked, in the canonical order", () => {
    assert.equal(redactField(["photograph", "signature", "face"], undefined), "signature,photograph");
    assert.equal(redactField(["signature", "stamp"], ["stamp"]), "stamp");
    assert.equal(redactField(undefined, ["stamp"]), "");
  });

  it("sends the hide list, style, and text flag", async () => {
    const file = new File([new Uint8Array([1])], "form.png", { type: "image/png" });
    let sent: FormData | null = null;
    await processImage(file, "http://127.0.0.1:8000", {
      concepts: ["signature", "stamp"],
      redact: ["photograph", "signature"],
      redactStyle: "blur",
      redactText: true,
      fetchImpl: async (_input, init) => {
        sent = init?.body as FormData;
        return jsonResponse(200, {
          boxes: [],
          overlay_png_base64: overlay,
          original_text: "",
          cleaned_text: "",
        });
      },
    });
    const form = sent as unknown as FormData;
    assert.equal(form.get("redact"), "signature");
    assert.equal(form.get("redact_style"), "blur");
    assert.equal(form.get("redact_text"), "true");
    assert.equal(form.get("extract"), "false");
  });

  it("defaults to no hiding, black, and no text check", async () => {
    const file = new File([new Uint8Array([1])], "form.png", { type: "image/png" });
    let sent: FormData | null = null;
    await processImage(file, "http://127.0.0.1:8000", {
      fetchImpl: async (_input, init) => {
        sent = init?.body as FormData;
        return jsonResponse(200, {
          boxes: [],
          overlay_png_base64: overlay,
          original_text: "",
          cleaned_text: "",
        });
      },
    });
    const form = sent as unknown as FormData;
    assert.equal(form.get("redact"), "");
    assert.equal(form.get("redact_style"), "black");
    assert.equal(form.get("redact_text"), "false");
  });
});

describe("parseProcessResponse share-safe fields", () => {
  const base = { boxes: [], overlay_png_base64: overlay, original_text: "a", cleaned_text: "a" };

  it("defaults the fields an older API does not send", () => {
    const parsed = parseProcessResponse(base);
    assert.equal(parsed.redacted_png_base64, null);
    assert.deepEqual(parsed.sensitive, []);
    assert.equal(parsed.shareable_text, null);
    assert.equal(parsed.image_text_hidden, false);
    assert.equal(parsed.document, null);
    assert.deepEqual(parsed.warnings, []);
  });

  it("keeps well-formed values and drops malformed items", () => {
    const parsed = parseProcessResponse({
      ...base,
      redacted_png_base64: overlay,
      sensitive: [
        { category: "phone", text: "07911 123456", source: "pattern" },
        { category: "name", text: 7, source: "model" },
        "junk",
      ],
      shareable_text: "Call [PHONE]",
      image_text_hidden: true,
      warnings: ["No stamp was found, so none is hidden.", 3],
    });
    assert.equal(parsed.redacted_png_base64, overlay);
    assert.deepEqual(parsed.sensitive, [
      { category: "phone", text: "07911 123456", source: "pattern" },
    ]);
    assert.equal(parsed.shareable_text, "Call [PHONE]");
    assert.equal(parsed.image_text_hidden, true);
    assert.deepEqual(parsed.warnings, ["No stamp was found, so none is hidden."]);
  });
});

describe("customChoice", () => {
  it("normalizes a custom name and maps preset names", () => {
    assert.deepEqual(customChoice("  QR   Code ", []), { kind: "custom", name: "qr code" });
    assert.deepEqual(customChoice("t-shirt", []), { kind: "custom", name: "t-shirt" });
    assert.deepEqual(customChoice("Stamp", []), { kind: "preset", name: "stamp" });
    assert.deepEqual(customChoice("photo", []), { kind: "preset", name: "photograph" });
  });

  it("rejects what the API would reject", () => {
    const message = (raw: string, existing: string[] = []) => {
      const choice = customChoice(raw, existing);
      return choice.kind === "error" ? choice.message : "";
    };
    assert.match(message(""), /Type what to find/);
    assert.match(message("company logo mark here"), /1 to 3 plain words/);
    assert.match(message("qr code 2"), /1 to 3 plain words/);
    assert.match(message("logo 🙂"), /1 to 3 plain words/);
    assert.match(message("a".repeat(31)), /1 to 3 plain words/);
    assert.match(message("Printed text"), /not text/);
    assert.match(message("logo", ["logo"]), /already on the list/);
    assert.match(message("face", ["logo", "qr code", "barcode"]), /up to 3/);
  });
});

describe("custom regions in the request", () => {
  it("sends custom names and lets them be hidden", async () => {
    const file = new File([new Uint8Array([1])], "letter.png", { type: "image/png" });
    let sent: FormData | null = null;
    await processImage(file, "http://127.0.0.1:8000", {
      concepts: ["signature"],
      custom: ["logo", "qr code"],
      redact: ["qr code", "signature", "face"],
      fetchImpl: async (_input, init) => {
        sent = init?.body as FormData;
        return jsonResponse(200, {
          boxes: [],
          overlay_png_base64: overlay,
          original_text: "",
          cleaned_text: "",
        });
      },
    });
    const form = sent as unknown as FormData;
    assert.equal(form.get("concepts"), "signature");
    assert.equal(form.get("custom"), "logo,qr code");
    assert.equal(form.get("redact"), "signature,qr code");
  });

  it("counts presets first, then custom regions in order", () => {
    const boxes = [
      { x: 0, y: 0, w: 1, h: 1, label: "qr code", score: 0.7 },
      { x: 0, y: 0, w: 1, h: 1, label: "stamp", score: 0.9 },
    ];
    assert.deepEqual(
      regionCounts(boxes, ["logo", "stamp", "qr code"]).map((row) => [row.label, row.count]),
      [
        ["stamp", 1],
        ["logo", 0],
        ["qr code", 1],
      ],
    );
  });

  it("keeps only well-formed palette colors", () => {
    const parsed = parseProcessResponse({
      boxes: [],
      overlay_png_base64: overlay,
      original_text: "",
      cleaned_text: "",
      palette: { logo: "#7c3aed", stamp: "red", "qr code": 3 },
    });
    assert.deepEqual(parsed.palette, { logo: "#7c3aed" });
  });
});
