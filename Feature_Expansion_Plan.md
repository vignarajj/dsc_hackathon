# Document Screenshot Cleaner — Feature Expansion Plan

**Goal:** turn a solid "OCR + proofread" tool into a memorable entry where **SAM 3.1 does real work** and the output is **something a person can act on**.
**Deadline:** Cerebral Valley portal, **4 November, 9:00 PM ET**. Target submission: **3 November** (one day of buffer).
**Baseline:** `main` at `003a890`. CI green. Backend 29 tests, frontend 22 tests.

---

## 1. The pitch this plan builds toward

> *"People photograph IDs, forms, and bank slips and send them over chat every day — signatures, faces, and account numbers included. Drop the photo in. SAM 3.1 finds the signature, the photo, the stamp, or anything you name. Muse reads the page, fixes it, pulls out the fields, and spots the phone numbers and ID numbers. One click gives you a share-safe copy."*

Every feature below exists to make one moment of that 90-second demo land. Anything that does not serve the pitch is out of scope.

### How judges will see it

| Judging lens | What we show | Feature |
|---|---|---|
| Use of Meta models | SAM is essential (redaction follows its masks), open-vocabulary prompts, SAM + Muse working together on each region | F1, F2, F5 |
| Impact / theme "Build for Your World" | Privacy for everyday document sharing; data out of messy photos | F1, F3 |
| Technical quality | Graceful degradation, anti-hallucination checks, tests, CI, streaming progress | §5, F6 |
| Demo / polish | Before/after slider, live progress, sample gallery, hosted URL | F6, F7 |

---

## 2. Scope

### In scope (ordered by priority — this is also the cut order, bottom first)

| ID | Feature | Priority | Est. |
|---|---|---|---|
| F0 | Live API spike (verify before building) | **Must** | 0.5 day |
| F1 | **Share-safe copy**: mask-shaped image redaction + sensitive-text redaction | **Must** | 1.5 days |
| F2 | **Custom region prompts** (open vocabulary) | **Must** | 0.5 day |
| F3 | **Structured extraction**: document type, key fields, JSON/CSV export | **Must** | 1 day |
| F6 | **Demo UX**: tabs, before/after slider, sample gallery, hover highlight | **Must** | 1 day |
| F4 | **Live progress** (streamed stages) | Should | 0.5 day |
| F5 | **Region understanding**: Muse describes each SAM region | Should | 0.5–1 day |
| F7 | **Ask the document** | Could | 0.5 day |
| F8 | Read aloud (browser speech) | Could | 1 hour |

### Explicitly out of scope
Multi-page PDF, batch upload, accounts/history, storing anything server-side, fact-checking/web search, click-to-segment point prompts (the parser supports `PromptPoint`, but it needs a second round trip and re-render — listed as a stretch idea only, §11).

---

## 3. F0 — Live API spike (do first, with `META_API_KEY`)

Same rule as the original Phase 0: **no UI is built on an unverified model behaviour.** A throwaway script in the scratchpad (not committed) runs each check on 6–10 real images (receipt, signed form, ID-style card with photo, handwritten note, chat screenshot, letter with logo and stamp).

| # | Question | How to check | Decision gate |
|---|---|---|---|
| S1 | Which **custom SAM prompts** return hits? | Run `logo`, `qr code`, `barcode`, `face`, `table`, `handwriting`, `id card`, `seal`, `checkbox` | Prompts that hit go into the suggestion chips for F2. Prompts that never hit go into the blocklist with a friendly message. |
| S2 | Does Muse return **valid JSON** reliably? | Ask for the F3 schema 10×; try Responses `text.format` JSON schema first, plain "return only JSON" second | If `text.format` works → use it. Else prompt-only + strict parse + one repair attempt. |
| S3 | Can Muse find **sensitive text spans** accurately? | Ask for exact substrings + category on the transcripts | Precision ≥ 90% on the set → ship F1b. Lower → ship regex detectors only, Muse as suggestions. |
| S4 | Can Muse vision give **pixel boxes for given words** (so sensitive text can be blacked out in the *image*)? | Ask for boxes of 3 known strings; overlay and eyeball | Boxes land on the words ≥ 80% → ship image text blackout (F1c). Otherwise **do not ship F1c**; the UI says "Text in the picture is not hidden — use the shareable text". Never fake it. |
| S5 | **Region description** quality on crops | Crop 10 SAM regions, ask for ≤ 12 words + any text inside | Useful on most → ship F5. |
| S6 | **Latency and size** per call | Time each call type; measure overlay PNG size on a 2048 px photo | Sets the timeout budget (§5.3) and the response-size decision (§5.4). |

**Output of F0:** a short table of results appended to the main plan doc §5, plus the decisions above. Half a day. If S1–S3 fail badly, F1/F3 still ship in their reduced forms — the plan has no dead ends.

---

## 4. Features

Each feature lists: user value · API contract · backend design · frontend design · edge cases · tests · acceptance criteria.

### F1 — Share-safe copy ⭐ (the headline)

**User value:** a copy of the document that is safe to send: signatures, faces/photos, and stamps hidden **following SAM's exact mask outline**, sensitive text masked, and location metadata stripped.

**Contract (additive, backward compatible):**

Request form fields:
- `redact` — comma list of region labels to hide. Omitted = no redaction (current behaviour). Must be a subset of the requested `concepts` (+ custom labels); otherwise HTTP 400.
- `redact_style` — `black` (default) or `blur`.
- `redact_text` — `true`/`false` (default `false`).

Response additions:
```json
{
  "redacted_png_base64": "<png, or null when redact is empty>",
  "sensitive": [
    { "category": "phone", "text": "+1 415 555 0101", "source": "pattern" },
    { "category": "id_number", "text": "X1234567", "source": "model" }
  ],
  "shareable_text": "Call [PHONE] about passport [ID_NUMBER]...",
  "warnings": []
}
```

**Backend design:**
- New module `backend/src/dsc_backend/redaction.py`:
  - `render_redacted(image, regions, labels, style) -> bytes`. Uses the same mask-at-box placement as `render_overlay`. Mask is **dilated 2–4 px** (Pillow `MaxFilter`) so edges do not leak. A region with no decodable mask falls back to its **full box** (safer). `blur` = strong Gaussian blur of the masked area (radius scaled to box size) — note in README that black is the safer choice.
  - Output re-encoded as PNG with **no EXIF/metadata** (Pillow does not copy it unless asked). Add a test that asserts no EXIF/GPS in the output.
- New module `backend/src/dsc_backend/privacy.py`:
  - `pattern_spans(text)`: regex backstop for email, phone (7+ digits with separators), long digit runs (card/account, Luhn check for cards), IBAN-like, dates of birth after "DOB". Deterministic, unit tested.
  - `model_spans(text)` via gateway (Muse, fenced prompt like the proofread): returns `[{category, text}]`.
  - **Anti-hallucination rule:** a model span is kept only if its `text` occurs **verbatim** in the transcript. Categories restricted to an enum: `phone, email, id_number, account_number, card_number, address, date_of_birth, name`. Unknown → dropped.
  - `mask_text(text, spans) -> str`: longest spans first, replaces every occurrence with `[CATEGORY]`.
- Runs **after** the transcript, **in parallel** with the proofread (TaskGroup). Masking is applied to the **proofread** text; spans are re-checked against the proofread (a span the proofread changed is matched in the transcript, and the warning `"Some sensitive text could not be matched after proofreading"` is added if it no longer appears).
- F1c (only if S4 passes): `model_word_boxes(data_url, spans)` → black boxes on the redacted image. Gated behind config `REDACT_IMAGE_TEXT=true`.

**Frontend design:**
- "Share-safe copy" panel: checkboxes for which regions to hide (defaults: signature, photograph, plus any custom), style toggle, "Also hide sensitive text" toggle.
- Result: **before/after slider** (original ↔ redacted), "Download share-safe image" (`<name>.safe.png`), "Copy shareable text", list of detected sensitive items with category chips.
- Honest note when F1c is off: "Text inside the picture is not hidden. Share the text version for that."

**Edge cases:** no regions found for chosen labels (redacted image = original, re-encoded, metadata stripped — say so); overlapping regions; boxes partly off-image (already clamped); huge masks; transcript empty (skip text redaction); model span appears multiple times (mask all); model returns invalid JSON (drop model spans, keep pattern spans, add warning — never fail the request).

**Tests:** mask-shaped fill matches the raster, dilation covers edge pixels, fallback to box when no mask, no EXIF in output, blur changes pixels only inside the mask; regex detectors (positive + negative cases, Luhn); verbatim-check drops invented spans; masking order with overlapping spans; contract tests for `redact` subset validation (400), omitted fields (unchanged response), model-failure degradation (200 + warning).

**Acceptance:** on the demo signed-form photo, signature and photo are fully hidden with no visible edge; phone/ID numbers masked in shareable text; downloaded file has no EXIF; existing clients unaffected.

---

### F2 — Custom region prompts (open vocabulary)

**User value:** "find anything" — type `logo`, `qr code`, `barcode` and SAM finds it. Shows off the most distinctive SAM 3.1 capability.

**Contract:** new form field `custom` — comma list, **max 3** phrases. Each phrase: lowercase, 1–3 words, letters/spaces/hyphens, ≤ 30 chars (`^[a-z][a-z -]{0,29}$`, ≤ 3 words). Blocklist from F0/S1 (`text`, `document`, `handwritten note`, `printed text`, `receipt`, …) → HTTP 400 with "SAM marks objects, not text. Try a stamp, logo, or QR code." Total SAM calls per request capped at **7** (4 presets + 3 custom).

**Backend:** extend `concepts_for_request` (or add `custom_concepts_for_request`) — normalize, dedupe against presets, validate. Labels flow through unchanged; overlay colours for custom labels come from a fixed 3-colour palette assigned by order (purple, teal, pink) — the response gets `"palette": {"logo": "#7c3aed", ...}` so the page legend always matches the image.

**Frontend:** "Find something else" input with suggestion chips from S1 (e.g. Logo · QR code · Barcode · Face), client-side validation mirroring the server, removable custom chips with their colour swatch.

**Edge cases:** custom equals a preset (`Stamp`) → treated as the preset; duplicates; unicode/emoji → rejected; prompt that returns nothing → chip shows "none found" (already supported by region counts).

**Tests:** validation table (valid, too long, 4 words, digits, blocklisted, duplicate, preset alias), call cap, palette in response, colours applied in overlay.

**Acceptance:** typing "logo" on the letterhead sample marks the logo in its own colour with a matching legend chip.

---

### F3 — Structured extraction

**User value:** the document becomes data: type, a one-line summary, key fields in a table, export to JSON/CSV.

**Contract:** request `extract=true|false` (UI default true). Response:
```json
"document": {
  "type": "invoice",
  "title": "Invoice #2041",
  "summary": "Invoice for consulting services, $1,200 due.",
  "fields": [
    { "label": "Invoice number", "value": "2041", "found_in_text": true },
    { "label": "Total due", "value": "$1,200", "found_in_text": true }
  ]
}
```
`type` enum: `invoice, receipt, form, id_document, letter, chat, note, screenshot, other`. Max 20 fields, label ≤ 40 chars, value ≤ 200 chars.

**Backend:** module `extraction.py`. Gateway method `extract(text) -> dict` (JSON per S2). Strict validation with Pydantic; one repair retry on invalid JSON is **not** an API retry of a failed call — it is a second prompt with the error; if still invalid → `document: null` + warning. **Grounding check:** `found_in_text` = normalized value (case/space/punctuation-insensitive) appears in the proofread text; ungrounded fields are shown with a "not found in text" marker, never silently trusted. Runs in parallel with proofread and privacy, so its input is the **transcript**; grounding is checked against both the transcript and the proofread text.

**Frontend:** "Data" tab: document type badge, summary, field table (copy per row), ungrounded rows visually flagged, **Download JSON** (`<name>.data.json`, includes fields + regions + text) and **Download CSV** (`label,value`; values quoted, formula-injection safe: prefix `=+-@` with `'`).

**Edge cases:** empty transcript (skip, `document: null`); chat/screenshot with no fields (summary only); non-English documents (labels in English, values verbatim — state in prompt).

**Tests:** schema validation, repair path, invalid twice → null + warning, grounding normalization, CSV escaping incl. formula injection, field caps.

**Acceptance:** invoice, receipt, and form samples each produce a correct type and ≥ 3 grounded fields.

---

### F4 — Live progress

**User value:** instead of a minute of spinner, the page shows each real step finishing: *Preparing image ✓ · Finding stamp, signature… ✓ · Reading text ✓ · Proofreading ✓ · Extracting fields ✓ · Building share-safe copy ✓*.

**Contract:** same endpoint; client sends `Accept: application/x-ndjson`. Server streams one JSON object per line: `{"event":"stage","stage":"segment","status":"done","detail":"stamp: 1"}` … final line `{"event":"result","data":{...}}` or `{"event":"error","status":502,"detail":"..."}`. Without that header the endpoint behaves exactly as today (curl, tests, old clients).

**Backend:** pipeline accepts an optional `on_stage` callback; `main.py` wraps it in a `StreamingResponse` fed by an `asyncio.Queue`. Validation errors (400/413/429) are still returned **before** streaming starts as normal HTTP errors. Client disconnect cancels the pipeline task (saves API spend — improves on today's Cancel).

**Frontend:** `process-client.ts` reads the body stream line by line (`ReadableStream` + `TextDecoder`), updates a stage list; Cancel aborts the fetch.

**Edge cases:** proxies buffering streams (send `X-Accel-Buffering: no`, `Cache-Control: no-cache`; verify on the chosen host in §8); partial last line; error after some stages.

**Tests:** backend streaming contract (stage order, final result equals non-stream result, error event), disconnect cancels gateway calls; frontend line parser with chunk splits mid-line.

---

### F5 — Region understanding

**User value:** each SAM region gets a plain-language note: *"Round stamp reading 'PAID 21 OCT 2026'"*, *"Handwritten signature"*, *"Passport-style photo of a person"*. SAM and Muse visibly cooperate.

**Contract:** request `describe=true|false`. Each box gains `"description": "..." | null`.

**Backend:** crop each region from the working image with 8% padding, upscale crops shorter than 256 px, encode, send to Muse vision with a fenced, short prompt (≤ 12 words, read any text inside, no speculation about identity). **Cap 8 regions** (highest score first), **concurrency 4** (`asyncio.Semaphore`). Per-region failure → `description: null`, never fails the request. Runs in parallel with proofread/extract/privacy.

**Privacy rule in the prompt:** never name or guess who a person is.

**Frontend:** descriptions in the region list and as tooltips on hover (F6).

**Tests:** crop math (padding, clamping, upscale), cap and ordering by score, semaphore limit, per-region failure isolation.

---

### F6 — Demo UX

1. **Result tabs** to hold the growing output: **Overview** (original ↔ overlay, region chips) · **Text** (current diff view) · **Data** (F3) · **Share-safe** (F1). Tabs are keyboard accessible (`role="tablist"`).
2. **Before/after slider** for overlay and share-safe views (pointer + keyboard arrows, `aria-valuenow`).
3. **Hover highlight:** absolutely positioned box outlines over the overlay image, scaled with `naturalWidth/clientWidth`; hovering a region chip or list row highlights its boxes; focus works the same for keyboard users.
4. **Sample gallery:** 4 one-click samples in `frontend/public/samples/`. **Only images you own or create** (no real personal data, no third-party documents). Make them realistic: a printed invoice with a "PAID" stamp, a filled form with a fake signature and a stock-free self-made photo placeholder, a handwritten note, a chat screenshot. Each sample is fetched as a `File` and goes through the same path as an upload.
5. **Empty and error states** reviewed for every new panel; dark mode and 375 px mobile width checked.
6. **Copy**: header subtitle names the three Meta-powered steps; footer line "Nothing you upload is stored."

---

### F7 — Ask the document (Could)

**Contract:** `POST /api/ask` JSON `{ "question": "...", "text": "<proofread text>", "fields": [...] }` → `{ "answer": "...", "quote": "<exact supporting line>" | null }`. Stateless (no image re-upload). Question ≤ 300 chars, text ≤ 20 000 chars. Rate-limited with the same limiter.

**Backend:** fenced prompt; answer only from the document; if not answerable → `"answer": "The document does not say."`. **Quote must appear verbatim** in the text, else `quote: null`.

**Frontend:** question box under the Text tab, 3 suggested questions per document type (e.g. invoice: "What is the total due?").

### F8 — Read aloud (Could)
`speechSynthesis` button on the Text tab, language from the document if known, stop button, hidden when the browser lacks support.

---

## 5. Cross-cutting design rules (the "no oversight" section)

### 5.1 Failure policy — core vs optional
| Step | On failure |
|---|---|
| Upload validation, image decode | HTTP 400/413 (unchanged) |
| SAM segmentation, transcription | HTTP 502 (unchanged) — the result is meaningless without them |
| Proofread | HTTP 502 (unchanged) |
| Extraction, privacy spans, region descriptions, word boxes | **Degrade**: field is `null`/empty, a human-readable string is added to `warnings[]`, HTTP 200 |

The page shows `warnings` in a quiet banner. This keeps optional features from making the core demo fragile.

### 5.2 Call graph and parallelism
```
prepare image
  ├─ SAM × N (≤7) ───────────────┐
  └─ transcribe ─┬─ proofread     │
                 ├─ extract       ├─► overlay + redaction render ─► response
                 ├─ privacy spans │
                 └─ (word boxes)  │
  regions ready ─► describe × ≤8 ┘
```
Critical path ≈ transcribe + slowest of (proofread, extract, privacy). Region descriptions start as soon as SAM finishes, overlapping with transcription.

### 5.3 Timeouts and cost
- Per-call timeout stays `UPSTREAM_TIMEOUT_SECONDS` (60).
- Add an **overall request budget** `REQUEST_BUDGET_SECONDS` (default 150): optional steps still running at the budget are cancelled and reported in `warnings`.
- Client timeout raised to **180 s** (budget + transfer).
- Max model calls per request: 7 SAM + 1 transcribe + 1 proofread + 1 extract (+1 repair) + 1 privacy + 8 describe (+1 word boxes) ≈ **21**. The UI toggles for Extract/Describe/Hide text let a user (and the hosted demo) keep it lower. Document the count in the README so the cost is transparent.
- Feature flags in config to disable each optional feature server-side (`FEATURE_EXTRACT`, `FEATURE_DESCRIBE`, `FEATURE_PRIVACY`, `FEATURE_IMAGE_TEXT_REDACTION`) — useful if the hosted key gets expensive.

### 5.4 Response size
Two full PNGs (overlay + redacted) of a 2048 px photo can reach 8–12 MB as base64. Decision after S6:
- If overlay PNG ≤ 3 MB → keep PNG for both.
- Otherwise → overlay as **JPEG q85** (`overlay_mime` field added; PNG stays default for small images), redacted stays **PNG** (no compression artefacts revealing hidden content). Field name stays `overlay_png_base64` for compatibility only if PNG; otherwise add `overlay_base64` + `overlay_mime`. Decide once, document in README.

### 5.5 Security and privacy
- Every model prompt that includes uploaded text fences it (`<transcript>`), as done for the proofread. One shared helper, tested once.
- No images or text are written to disk or logs. Logs keep counts and timings only (as today). README states it.
- Rate limit covers `/api/process` and `/api/ask`.
- CSV export escapes formula injection.
- Redacted output never derives from blur alone when style is `black`; blur is documented as weaker.
- Model output is never trusted as HTML (React escapes; no `dangerouslySetInnerHTML`).

### 5.6 Code organisation
`pipeline.py` must stay readable. New modules, each with its own tests:
```
backend/src/dsc_backend/
  pipeline.py        # orchestration only
  redaction.py       # F1 image redaction
  privacy.py         # F1 sensitive-text detection + masking
  extraction.py      # F3 schema, validation, grounding
  describe.py        # F5 crops + descriptions
  prompts.py         # all prompt templates + fence helper
  progress.py        # F4 stage events
  meta.py            # gateway (new methods: extract, sensitive_spans, describe_region, ask)
frontend/src/
  app/cleaner.tsx            # page shell + upload form
  app/results/*.tsx          # Overview, TextTab, DataTab, ShareTab, CompareSlider, RegionList
  lib/process-client.ts      # + stream reader
  lib/exports.ts             # JSON/CSV builders
```
`MetaGateway` protocol grows; `FakeGateway` in tests implements every method with deterministic outputs and per-method failure switches.

### 5.7 Backward compatibility
All request fields are optional with today's defaults; all response fields are additive. The existing 29 backend contract tests must keep passing unmodified (except where they assert the full key set).

---

## 6. Testing and quality gates

| Layer | What | Where |
|---|---|---|
| Backend unit | each new module | `backend/tests/test_<module>.py` |
| Backend contract | new fields, defaults, 400s, degradation, streaming | `backend/tests/test_process.py`, `test_stream.py`, `test_ask.py` |
| Frontend unit | stream parser, exports (CSV escaping), validation of custom prompts, slider maths | `frontend/src/lib/*.test.ts` |
| **E2E (new, in CI)** | Playwright drives the built page against the backend running with a **fake gateway** (`backend/tests/fake_server.py`): upload sample → all tabs render → downloads produce files → cancel works | `frontend/e2e/*.spec.ts`, new CI job |
| Live smoke (manual, needs key) | `backend/scripts/smoke.py` runs the 6–10 sample set against the real API and prints a pass/fail table + timings | run before each demo recording and after deploy |
| Quality bar | ruff, eslint, typecheck, build, all tests green on every push | existing CI |

**Evaluation sheet** (kept in the plan doc): per sample — regions expected vs found, fields correct, sensitive items caught/missed, total time. Run it after F0 and again before freeze. Numbers like "caught 27/29 sensitive items across 8 documents" are excellent README and demo material.

---

## 7. Schedule (12 days)

| Date | Work | Exit criterion |
|---|---|---|
| **Thu 23 Oct** | F0 spike (needs your key) · create real sample images | Decision table filled in |
| **Fri 24 Oct** | Refactor: `prompts.py`, gateway protocol, `warnings`, failure policy, request budget | All existing tests green, no behaviour change |
| **Sat 25 Oct** | F1a image redaction + F2 custom prompts (backend + UI) | Tests + browser check |
| **Sun 26 Oct** | F1b sensitive text (patterns + model + masking) · F1c if S4 passed | Tests + live smoke |
| **Mon 27 Oct** | F3 extraction + exports | Tests + live smoke on invoice/receipt/form |
| **Tue 28 Oct** | F6 tabs, slider, hover, gallery | E2E passes in CI |
| **Wed 29 Oct** | F4 streaming progress · F5 region descriptions | Tests + live smoke |
| **Thu 30 Oct** | F7 ask + F8 read aloud **only if on schedule**; otherwise bug fixing | — |
| **Fri 31 Oct** | **Feature freeze.** Evaluation sheet run, fixes, a11y/mobile/dark pass | No open bugs above cosmetic |
| **Sat 1 Nov** | Deploy (backend: Railway/Render/Fly; frontend: Vercel), rate limit on, streaming verified through the host | Live smoke passes on the public URL |
| **Sun 2 Nov** | Record final demo, README rewrite, screenshots/GIF, About section | Video 60–90 s, README reviewed |
| **Mon 3 Nov** | **Submit.** Make repo public. Final check of links | Submitted |
| Tue 4 Nov | Buffer only | — |

**If behind schedule, cut in this order:** F8 → F7 → F5 → F4 → F1c. **Never cut** F1a/b, F2, F3, F6 — they carry the demo.

---

## 8. Deployment checklist
- Backend env: `META_API_KEY`, `CORS_ORIGINS=<frontend URL>`, `RATE_LIMIT_PER_MINUTE=5`, feature flags, `REQUEST_BUDGET_SECONDS`.
- Run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>` so the rate limit sees real IPs.
- Confirm the host allows ≥ 180 s requests and does not buffer NDJSON streams.
- Frontend env: `NEXT_PUBLIC_API_BASE_URL=<backend URL>` at build time.
- Set a spend alert on the Meta key. Plan to take the URL down after judging.
- `/api/health` monitored once before recording and once before submitting.

---

## 9. Demo script (90 seconds)

| Time | Shot | Line |
|---|---|---|
| 0–10 s | Phone photo of a filled form with signature, ID photo, stamp | "We send photos like this every day — signature, face and ID number included." |
| 10–25 s | Click sample → live progress stages tick | "SAM 3.1 finds the regions while Muse reads the page." |
| 25–40 s | Overview: masks + region notes; type "QR code" → found | "SAM finds anything you can name." |
| 40–55 s | Data tab: type badge, fields, JSON export | "Muse turns the photo into data — and checks every field against the text." |
| 55–75 s | Share-safe tab: drag the slider; sensitive text masked | "One click: signature, photo and ID number hidden, location data stripped." |
| 75–90 s | Back to title; one sentence on who it helps | "Built for the paperwork in everyone's world." |

---

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Muse JSON unreliable | Medium | F3/F1b weaker | S2 gate; repair attempt; degrade with warnings |
| Muse cannot box words (S4) | High | No in-image text blackout | Honest UI note; text redaction still shipped |
| Latency > 2 min with all features | Medium | Bad demo | Parallelism, budget, toggles, streaming progress makes waiting visible |
| Large responses slow on hosting | Medium | Slow page | §5.4 JPEG overlay decision |
| Host buffers streams | Low–Med | No live progress | Headers; fall back to non-stream automatically when no stage arrives within 5 s |
| API cost on public URL | Medium | Bill | Rate limit, feature flags, spend alert, take down after judging |
| Sample images contain real personal data | Low | Reputational | Only self-made samples; reviewed before commit |
| Scope creep | High | Missed deadline | Feature freeze 31 Oct; cut order in §7 |

---

## 11. Stretch ideas (only after submission-ready)
- **Click to add a region** SAM missed, using `PromptPoint` object prompts from `meta-sam-parser` (`build_object_prompt`).
- **Page auto-flatten**: SAM `rectangle` mask of the page → perspective-correct crop.
- **Translate** the cleaned text.

---

## 12. Definition of done (submission)
- [ ] F1, F2, F3, F6 shipped; F4/F5 shipped or consciously cut
- [ ] All CI jobs green, including E2E
- [ ] Live smoke passes on the public URL
- [ ] Evaluation sheet results in README
- [ ] New demo video (60–90 s) in `demo/` and linked
- [ ] README: pitch, screenshot/GIF of the share-safe slider, "How Meta models are used" table, architecture diagram, privacy statement, call-count/cost note
- [ ] Repo public, About section set, submitted on the portal by 3 Nov

---

## 13. Status tracker

The work after feature-complete (live checks, deploy, demo, submission) is
tracked in `docs/LAUNCH.md`. The rows below from L1 on are kept here for
history; their current status lives there.

Update this table in every commit that changes a row. `Status` is one of
`Not Started`, `In Progress`, `Done`, or `Blocked` (with the blocker named).
`Tests`, `Docs`, and `Commit` turn `Yes` when the work delivers them. Every
row below was built and checked without live Meta calls unless its notes say
otherwise; checks on real photos are tracked as their own rows.

| ID | Work item | Ref | Status | Tests | Docs | Commit | Notes |
|----|-----------|-----|--------|-------|------|--------|-------|
| F0 | Live API spike | §3 | Done | No | Yes | Yes | `8ceaef4`. About 250 live calls on 8 generated documents; results and decisions in the main plan §5.1. Scripts stay out of the repo, as planned. |
| F1a | Share-safe image: mask-shaped hiding, no metadata | §4 F1 | Done | Yes | Yes | Yes | `f57144b`. SAM found no signatures in F0, so Muse vision boxes them. `photograph` is sent to SAM as `photo`. |
| F1b | Sensitive text: patterns, Muse spans, masking | §4 F1 | Done | Yes | Yes | Yes | `f6162f9`. Verbatim check drops invented spans. Surnames and sort codes added after the live run. |
| F1c | Black out sensitive text in the image | §4 F1 | Done | Yes | Yes | Yes | `52d86a8`. Behind `REDACT_IMAGE_TEXT`, off until checked on real photos. |
| F1 UI | Share-safe panel, slider, downloads | §4 F1 | Done | Yes | Yes | Yes | `5f8df1e`. |
| F2 | Custom region prompts | §4 F2 | Done | Yes | Yes | Yes | `c6a3633`. Up to 3 names, blocklist from F0, palette in the response. |
| F3 | Structured extraction, JSON and CSV export | §4 F3 | Done | Yes | Yes | Yes | `ad12bc4`. Strict schema, one repair prompt, grounding check, CSV formula defusing. |
| F6 | Demo UX: tabs, slider, highlight, samples, E2E | §4 F6, §6 | Done | Yes | Yes | Yes | `2f69deb`. Playwright against a fake gateway, desktop and 375 px dark; CI job added; it passed on GitHub for the first time in the merge (M1). |
| F4 | Live progress (NDJSON stream) | §4 F4 | Done | Yes | Yes | Yes | `f1749f7`. Disconnect cancels the work. The 5 s fallback to a plain request was left out on purpose: it would send the request twice. |
| F5 | Region descriptions | §4 F5 | Done | Yes | Yes | Yes | `a23ae58`. Off by default on the page to save calls; the plan had it on. |
| F7 | Ask the document | §4 F7 | Done | Yes | Yes | Yes | `1ba571f`. `POST /api/ask`, verbatim quotes only, shared rate limit. |
| D1 | READMEs and docs match the code, status tracker | §12 | Done | No | Yes | Yes | Root README rewritten; backend and frontend READMEs corrected; screenshot retaken. |
| F8 | Read aloud | §4 F8 | Done | Yes | Yes | Yes | Browser speech, no API call. Spoken in sentence-sized pieces; hidden without speech. No language is set, since the API does not report one. |
| H1 | Overall request budget (`REQUEST_BUDGET_SECONDS`) | §5.3 | Done | Yes | Yes | Yes | 150 s default for the optional steps; a late step is cancelled and named in `warnings`. Core steps are never cut. |
| H2 | Server-side feature flags | §5.3 | Done | Yes | Yes | Yes | `FEATURE_EXTRACT`, `FEATURE_DESCRIBE`, `FEATURE_PRIVACY`, default on; image text keeps `REDACT_IMAGE_TEXT`. `GET /api/config` lets the page mark options that are off. |
| H3 | Live smoke script (`backend/scripts/smoke.py`) | §6 | Done | Yes | Yes | Yes | Tested against the fake gateway; run live on 27 Oct (§14). Sends nothing without `--yes`. `--describe` adds region descriptions, `--delay` stays under a rate limit, and a page named `receipt` gets receipt checks. Its table feeds L1 and L2. |
| H4 | Prompts in one `prompts.py` | §5.6 | Done | Yes | Yes | Yes | Every prompt and the fence helper are in `prompts.py`; the span schema moved to `privacy.py` beside the other schemas. A pure move: all 13 requests the gateway sends were compared before and after and are byte for byte the same. |
| L1 | Acceptance checks on real photos (F1, F2, F3) | §4 | In Progress | No | Yes | Yes | Run on the four generated samples on 27 Oct, 40 calls (§14): F1, F3 and F7 pass, F2 partly. A second run on 2 Nov, 28 calls (§15): receipt, F1c, descriptions and the QR code pass. Still open: real phone photos and real signatures. |
| L2 | Evaluation sheet | §6 | In Progress | No | Yes | Yes | Numbers for the four generated samples are in §14 and the README. Real-photo numbers wait on photos. |
| UI1 | UI polish: theme toggle, one font family, sea-blue and green palette, scroll to progress and result | §4 F6 | Done | Yes | Yes | Yes | `3430461`, `3ed9f03`. Auto / Light / Dark control with a stored choice and no flash; the serif font dropped; options grouped; the page scrolls to the progress and the result. 4 new browser tests (34 pass), e2e ports configurable. |
| R1a | Deploy configs: `backend/Dockerfile`, `render.yaml`, `frontend/vercel.json`, `docs/DEPLOY.md` | §8 | Done | No | Yes | Yes | The image's install and start commands were run outside a container (no base image could be pulled here), and the container was not built. `FORWARDED_ALLOW_IPS` trusts private ranges only; `*` would let visitors skip the rate limit. |
| R1b | Deploy, rate limit, spend alert, streaming through the host | §8 | In Progress | No | Yes | Yes | Live on 2 Nov: API on Render (Free, by hand), page on Vercel; streaming, CORS and the smoke test pass (§16). The limit is shared by all visitors, set to 10. Open: the spend alert on the key. |
| R2 | Demo video and final README | §9, §12 | In Progress | No | Yes | No | README has the live link, the public-copy results, and the hosting section. Missing: the new demo video and a GIF. |
| R3 | Repo public, submit on the portal | §12 | Not Started | No | No | No | Target 3 Nov. |
| M1 | Merge into `main` | — | Done | Yes | Yes | Yes | vignarajj/dsc_hackathon#1, rebase-merged; `main` at `07a4401`. All CI jobs green, e2e for the first time on GitHub. |
| M2 | Launch tracker and live-run results on `main` | — | Done | No | Yes | Yes | `docs/LAUNCH.md` and §14 pushed straight to `main` as a fast-forward (`c3f5678`), two docs-only commits. |

---

## 14. Live run on the four samples (27 Oct 2026)

**Setup.** The real API and key, the four sample pages in
`frontend/public/samples/` (generated for this app, 1600 px, so cleaner than
real phone photos), and the page's default choices: four regions, signature
and photograph hidden, personal details masked, key fields on. A throwaway
launcher in the scratchpad counted every model call and refused any past the
cap of 40. It used exactly 40 and none failed; no extraction needed a repair
prompt. `backend/scripts/smoke.py` ran the four pages (36 calls), then 3 calls
for the logo check and 1 for a question.

| Page | Type | Regions found | Fields found in the text | Drawn-in personal details hidden | Time |
|---|---|---|---|---|---|
| chat | chat, right | rectangle x8 (the chat bubbles) | 10 of 10 | 6 of 6 | 17.0 s |
| handwritten note | note, right | none | 11 of 11 | 3 of 3 | 8.7 s |
| invoice | invoice, right | stamp | 19 of 19 | 5 of 5 | 17.1 s |
| signed form | form, right | stamp, signature, photograph | 14 of 14 | 6 of 6 | 15.8 s |
| **Total** | **4 of 4** | | **54 of 54** | **20 of 20** | 8.7 to 17.1 s |

"Hidden" means the item, as I drew it into the page, no longer appears in the
shareable text. Five more items were masked that were not on my list, all
personal: two sort codes and the names "Sam", "Ana", and "R. Shah".

**Acceptance checks (§4).**

| Check | Result |
|---|---|
| F1: signature and photo fully hidden on the signed form | Pass. Both are fully covered in the share-safe image. The signature area is a box, larger than the signature and including its label, because Muse boxes have no mask. |
| F1: phone and ID numbers masked in the shareable text | Pass, 6 of 6 on the form. |
| F1: no metadata in the downloaded file | Pass. None of the four share-safe files has EXIF. The samples had none to start with; the unit test strips real EXIF. |
| F1: no false signature on pages without one | Pass. The Muse lookup returned nothing for the chat, the note, and the invoice. |
| F2: "logo" marks the logo in its own color | Partly. It boxed the logo mark (58 px, score 0.85) in purple, with the legend color returned. It also boxed the round PAID stamp as a second "logo" (score 0.73), and the wordmark beside the mark was not covered. This matches F0. |
| F3: right type and 3 or more fields found in the text | Pass for the invoice (19 fields) and the form (14). The receipt was not in these four pages. |
| F7: ask a question | Pass. "What is the total due?" gave "The total due is $1,200.00." with a quote taken word for word from the page. |

**Time per call** (40 calls, median / slowest): segment 1.7 / 4.0 s (17
calls), transcribe 5.2 / 9.8 s, proofread 3.1 / 8.7 s, extract 6.0 / 7.4 s,
personal details 4.9 / 12.3 s, signature lookup 3.0 / 5.0 s, ask 1.6 s.

**Response size (§5.4).** At 1600 px the overlay PNG was 291 to 939 KB and the
share-safe PNG 261 to 839 KB, well under the 3 MB line, so both stay PNG.
Real photos at 2048 px compress worse, so this is rechecked on them.

**Decisions.**
- Muse signature boxes stay: right on the one generated signature, no false
  positives on three other pages. Not yet proven on a real signature.
- `REDACT_IMAGE_TEXT` (F1c) stays off, and region descriptions stay off by
  default on the page. Neither was run, to stay within the cap.
- The PNG overlay stays.

**Not covered by this run:** real phone photos, real handwritten signatures,
F1c, region descriptions, a receipt, and streaming through a host. They need
photos and more calls; tracked in `docs/LAUNCH.md`.

---

## 15. Second live run: receipt, F1c, descriptions, QR code (2 Nov 2026)

**Setup.** No phone photos were available, so this run used a generated
receipt (invented store and customer, rotated and noised like a photo, 1240 x
1800), the signed form, and the invoice. The real API and key ran behind a
throwaway launcher that counted every model call and refused any past a cap of
35, with `REDACT_IMAGE_TEXT=true`. It used 28 calls; none failed and none was
refused.

| Check | Calls | Result |
|---|---|---|
| Receipt through `smoke.py --ask` | 11 | Pass. Type `receipt`, 17 of 17 fields found in the text, 4 kinds of personal details masked, "What was the total?" gave 21.32. 2 warnings were not inspected. 73.6 s, see below. |
| Signed form, F1c and descriptions on | 13 | F1c pass: all 7 sensitive values (name, date of birth, phone, email, address, passport number, "R. Shah") are blacked out in the picture, and the signature and photo are hidden. No warnings. |
| "QR code" on the invoice | 4 | Pass. Found with score 0.97, a tight box, next to the stamp (0.90). |
| EXIF and GPS, fake gateway | 0 | Pass. A JPEG with GPS and camera tags gave a share-safe PNG and an overlay with no metadata. |

**Region descriptions** (3 calls on the form): all three regions came back
with a short description and no warning, and none names or guesses a person
("Cartoon smiling face with dark hair, blue shirt, light background").

**What F1c costs.** It adds one call after the personal-details step, so it
runs in sequence: 16.1 s on the form and 28.7 s on the receipt. The form took
48.1 s end to end with descriptions and F1c (15.8 s on 27 Oct without them).
The receipt took 73.6 s, which also had a 37.3 s personal-details call (median
4.9 s on 27 Oct). The boxes are wider than the words, so they cover the
labels beside the values: parts of "Full name", "Date of birth", "Phone",
"Email", "Address", "Passport no." and the "Checked by" header were clipped.
Nothing sensitive was left readable on the form. The receipt's picture was not
saved, so its F1c output was not looked at.

**Time per call** (28 calls, in seconds): segment 1.9 to 4.1 (10 calls),
transcribe 7.4 to 13.8, proofread 4.3 to 6.0, extract 9.9 to 10.9, personal
details 7.9 and 37.3, signature lookup 4.5 and 6.1, descriptions 5.3 to 14.8,
text boxes 16.1 and 28.7, ask 2.9.

**Decisions.**
- F1c stays off by default and on the public copy: it works on the generated
  form, but adds 16 to 29 s and clips labels. It is not checked on real photos.
- Region descriptions work and stay off by default on the page, to save up to
  8 calls per image.
- The QR code prompt is safe to use in the demo.

**Still not covered:** real phone photos, real handwritten signatures, F1c on
a receipt's picture, and streaming through a host.

---

## 16. Public copy checks (2 Nov 2026)

**Setup.** The API on Render (Docker, Free instance, set up by hand from
`backend/Dockerfile`) at `https://dsc-api-xxzv.onrender.com`, the page on Vercel
at `https://dsc-hackathon.vercel.app`. Region descriptions and the text
blackout in the picture are off. A cap of 45 model calls was agreed; the
checks used about 43 (3 for the stream, about 40 for the smoke test).

| Check | Result |
|---|---|
| `GET /api/health` and `/api/config` | Pass. `{"status":"ok"}` in 0.2 s; descriptions off, text blackout off. |
| CORS | Pass. The page's origin is allowed; another origin gets "Disallowed CORS origin". |
| Page points at the API | Pass. The built page carries the Render address, not `127.0.0.1`. |
| Progress arrives line by line | Pass. 11 lines over 21.7 s through Render and its Cloudflare front, `content-type: application/x-ndjson`, `cache-control: no-cache`. |
| Rate limit holds against a faked address | Pass. Fresh fake `X-Forwarded-For` values did not get past a tripped limit. |
| Rate limit value | Off from the plan. Requests 4 to 6 of six bad uploads were 429, twice, after a 75 s quiet window, so the server allows 3 a minute, not the 5 the blueprint sets. The code only counts allowed requests, so the likeliest cause is `RATE_LIMIT_PER_MINUTE` being set to 3 on the service. Not read from the dashboard. |
| `smoke.py --yes --ask --delay 21` | Pass, 4 of 4 pages: right types, 14, 11, 18 and 17 fields all found in the text, one question answered per page. |

**Time.** 22.2 to 36.5 s per page with a question, against 8.7 to 17.1 s per
page locally on 27 Oct. Render's Free instance, Cloudflare in front, and
Meta's own latency all differ between the two runs; this was not separated.

**Phone check (Pixel 3, LineageOS, Jelly browser, over Wi-Fi), driven with
Maestro.** The page rendered at phone width in dark mode. A full clean of the
invoice sample (about 9 calls) gave the Overview tab with the two "No ... was
found, so none is hidden" notes, the Data tab (type, summary, 18 fields with
Copy buttons), and the Share-safe tab (slider, download, shareable text with
`[PHONE]` and `[EMAIL]`). Cancel appeared while a clean ran, and pressing it
returned the page to "Clean screenshot" (about 6 calls started). The phone has
no SIM, so it shared this machine's Wi-Fi and was not a second network.

**Second-network check: failed (2 Nov, 13:27).** The Pixel was on an
iPhone hotspot with public IP `106.217.113.69`; this Mac was on `103.169.237.202`.
While the Mac kept its limit tripped with a bad upload every 12 s (400, 400,
400, 429, 429, repeating), the phone pressed Clean and the page showed "Too many
requests. Wait a minute and try again." The phone had sent no earlier request
from that address. No model call was spent. So every visitor shares one limit on
Render: the case `docs/DEPLOY.md` §1 warns about. The likely cause is that
Render's proxy does not connect from the private ranges in
`FORWARDED_ALLOW_IPS`, so `X-Forwarded-For` is not trusted and the proxy's
address is the key. This fails safe for spend, but on the public copy a few
requests a minute across all visitors is all anyone gets.

**Decision and check (2 Nov).** `RATE_LIMIT_PER_MINUTE` was raised to 10 on the
service, shared by all visitors. Twelve bad uploads then gave ten 400s and two
429s, so the service honours the value; the earlier limit of 3 was whatever it
was set to then. Health and the CORS preflight still pass.

**Still open:** the spend alert on the key, and keying the limit on the visitor
(not worked out; the shared limit is the accepted trade-off).

**Rerun on the public copy (2 Nov, later).** `smoke.py --yes --ask` on the four
samples and the generated receipt, about 50 calls: 5 of 5 pages passed, with
20, 13, 10, 10 and 17 fields found in the text, one correct answer each, and
15.8 to 68.6 s a page. The receipt took 68.6 s with the text blackout off, so
its 73.6 s earlier was not mostly that step; which step is slow on it was not
measured. GitHub CI is green on `main`, including the browser tests, which
could not start locally because another process held port 3100.

**Phone recording (2 Nov, about 9 calls).** A Pixel 3 screen recording of a full
clean of the signed form on the public copy (71.6 s, cut and sped up to an
18 s GIF, `docs/phone-demo.gif`). The page's step list, the Overview, and the
Share-safe slider with the photo and signature hidden all showed on the phone.
The raw recording is not in the repo.

---

## 17. UI review and a recorded session (2 Nov 2026)

**What was found.** The page had a light and a dark palette but followed only the
system setting, so on a Mac set to dark there was no light mode to see and no
way to switch. It loaded three font families at once (a serif for headings,
a sans for the interface, a mono for the text boxes). The hero had a large gap
above the title on desktop; the tagline appeared in the header, the hero and
the footer; the options were a long flat list; the Clean button looked
disabled and gave no reason; and after pressing it the progress and the result
sat below the whole form, out of view. The brown and cream colours were also
judged plain, and the red accent clashed with the red "Stamp" region colour.

**What changed.** An Auto / Light / Dark control in the header (a stored choice
is set on `<html>` before the first paint); one sans family, with the mono kept
only in the text boxes; one options card; a clear primary button with a hint when
no file is chosen; scrolling to the progress and then the result; and a
sea-blue accent with a green partner (every text and button pair at least 4.5:1)
in a mist-white light theme and a deep-sea dark theme. A stale-CSS surprise on
one local build (a changed stylesheet not rebuilt) was fixed by a clean build.

**Checks.** Lint, typecheck, 64 unit tests, 200 backend tests, and 34 browser
tests (17 on desktop, 17 on a 375 px phone) all pass, 4 of the 17 new. A manual
Playwright pass checked the toggle, a stored choice, a stored Light on a dark
system, the system setting, and the scroll, on desktop and a 390 px phone.

**Recorded session on the public copy.** A Playwright run (video and
screenshots) and a second pass for clean screenshots, then a Pixel 3 recording
with Maestro: about 37 calls in all (10 for the video run with one question,
9 for a phone-sized run, 9 for the screenshots, 9 for the Pixel). The results
are in `demo/ui-session.webm`, `docs/ui-session.gif`, `docs/phone-demo.gif` and
`docs/screenshots/`, and in the README. The new page went live on Vercel about
30 seconds after each push.

