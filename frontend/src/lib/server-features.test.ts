import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { DEFAULT_FEATURES, fetchFeatures } from "./server-features.ts";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("fetchFeatures", () => {
  it("reads the features the API reports", async () => {
    const features = await fetchFeatures("http://127.0.0.1:8000/", async (input) => {
      assert.equal(input, "http://127.0.0.1:8000/api/config");
      return json(200, {
        features: { extract: false, describe: true, privacy: false, image_text: true },
      });
    });
    assert.deepEqual(features, { extract: false, describe: true, privacy: false, imageText: true });
  });

  it("keeps the defaults for an older API, an error, or a bad body", async () => {
    assert.deepEqual(await fetchFeatures("http://x", async () => json(404, {})), DEFAULT_FEATURES);
    assert.deepEqual(
      await fetchFeatures("http://x", async () => {
        throw new Error("down");
      }),
      DEFAULT_FEATURES,
    );
    assert.deepEqual(
      await fetchFeatures("http://x", async () => json(200, { features: { extract: "no" } })),
      DEFAULT_FEATURES,
    );
  });
});
