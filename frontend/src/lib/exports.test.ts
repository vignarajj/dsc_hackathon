import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { dataJson, documentTypeLabel, fieldsCsv } from "./exports.ts";
import { parseProcessResponse } from "./process-client.ts";

describe("fieldsCsv", () => {
  it("quotes every value and doubles quotes", () => {
    assert.equal(
      fieldsCsv([
        { label: "Total due", value: "$1,200.00", found_in_text: true },
        { label: 'Note "A"', value: "line one\nline two", found_in_text: false },
      ]),
      'label,value\r\n"Total due","$1,200.00"\r\n"Note ""A""","line one\nline two"\r\n',
    );
  });

  it("defuses cells a spreadsheet would run as a formula", () => {
    const csv = fieldsCsv([
      { label: "=HYPERLINK(1)", value: "+44 113 496 0732", found_in_text: true },
      { label: "Balance", value: "-12.50", found_in_text: true },
      { label: "Handle", value: "@ana", found_in_text: true },
    ]);
    assert.equal(
      csv,
      'label,value\r\n"\'=HYPERLINK(1)","\'+44 113 496 0732"\r\n"Balance","\'-12.50"\r\n"Handle","\'@ana"\r\n',
    );
  });

  it("writes only the header for no fields", () => {
    assert.equal(fieldsCsv([]), "label,value\r\n");
  });
});

describe("dataJson", () => {
  it("includes the document, regions, and both texts", () => {
    const result = parseProcessResponse({
      boxes: [{ x: 1, y: 2, w: 3, h: 4, label: "stamp", score: 0.9 }],
      overlay_png_base64: "iVBORw0KGgo=",
      original_text: "Reciept",
      cleaned_text: "Receipt",
      document: {
        type: "receipt",
        title: "Receipt",
        summary: "A receipt.",
        fields: [{ label: "Total", value: "4.20", found_in_text: true }, { label: 3 }],
      },
    });
    const parsed = JSON.parse(dataJson(result, "shop.jpg"));
    assert.equal(parsed.file, "shop.jpg");
    assert.deepEqual(parsed.document.fields, [{ label: "Total", value: "4.20", found_in_text: true }]);
    assert.equal(parsed.regions[0].label, "stamp");
    assert.deepEqual(parsed.text, { transcription: "Reciept", proofread: "Receipt" });
  });
});

describe("documentTypeLabel", () => {
  it("names known types and spells out others", () => {
    assert.equal(documentTypeLabel("id_document"), "ID document");
    assert.equal(documentTypeLabel("bank_slip"), "bank slip");
  });
});
