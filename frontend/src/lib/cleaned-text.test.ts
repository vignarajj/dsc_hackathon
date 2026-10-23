import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  categoryLabel,
  cleanedMarkdownName,
  dataCsvName,
  dataJsonName,
  markdownForCleanedText,
  overlayPngName,
  safePngName,
} from "./cleaned-text.ts";

describe("markdownForCleanedText", () => {
  it("keeps line breaks and ends with one newline", () => {
    assert.equal(markdownForCleanedText("Hello\r\nWorld"), "Hello\nWorld\n");
    assert.equal(markdownForCleanedText("Hello\n"), "Hello\n");
  });

  it("returns nothing for blank text", () => {
    assert.equal(markdownForCleanedText("  \n"), "");
  });
});

describe("cleanedMarkdownName", () => {
  it("uses the upload name and a markdown extension", () => {
    assert.equal(cleanedMarkdownName("note.png"), "note.cleaned.md");
    assert.equal(cleanedMarkdownName("My Scan.JPEG"), "My-Scan.cleaned.md");
    assert.equal(cleanedMarkdownName("weird?.png"), "weird.cleaned.md");
    assert.equal(cleanedMarkdownName(""), "screenshot.cleaned.md");
  });
});

describe("overlayPngName", () => {
  it("uses the upload name and a png extension", () => {
    assert.equal(overlayPngName("My Scan.JPEG"), "My-Scan.overlay.png");
    assert.equal(overlayPngName(""), "screenshot.overlay.png");
  });
});

describe("safePngName", () => {
  it("uses the upload name and a safe png extension", () => {
    assert.equal(safePngName("My Scan.JPEG"), "My-Scan.safe.png");
    assert.equal(safePngName(""), "screenshot.safe.png");
  });
});

describe("categoryLabel", () => {
  it("names the known categories and spells out others", () => {
    assert.equal(categoryLabel("date_of_birth"), "Date of birth");
    assert.equal(categoryLabel("id_number"), "ID number");
    assert.equal(categoryLabel("tax_code"), "tax code");
  });
});

describe("data file names", () => {
  it("use the upload name", () => {
    assert.equal(dataJsonName("My Scan.JPEG"), "My-Scan.data.json");
    assert.equal(dataCsvName("bill.png"), "bill.data.csv");
  });
});
