# Document / Screenshot Cleaner with SAM 3.1
## Meta Global AI Developer Hackathon — Complete Execution Plan

**Track:** Indie Developer  
**Theme:** Build for Your World  
**Timeline:** 2–3 focused days  
**Core Goal:** Ship a working, demo-ready tool that uses Meta’s models

---

## 1. Product Objective

Build a simple tool that:
- Accepts a screenshot or photo of a document
- Uses **SAM 3.1** to segment relevant regions (text blocks, stamps, signatures, noise, etc.)
- Extracts the content
- Uses a **Muse model** to proofread and clean the text
- Shows the original image (with masks) + cleaned result side-by-side

This is sufficient for a strong demo. Additional features are only added after the core flow is solid.

---

## 2. Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Frontend** | Next.js (React) | Fast upload UI + image overlay |
| **Backend** | FastAPI (Python) | Simple, matches your experience |
| **Segmentation** | SAM 3.1 via Meta Model API | Primary Meta tooling |
| **Text Processing** | Muse (Spark / Wonder) via Meta Model API | Proofreading & cleanup |
| **Image Processing** | Pillow / OpenCV | Mask overlay and basic handling |
| **OCR (default)** | Muse vision (image understanding) | Default path — zero extra deps |
| **OCR (fallback)** | EasyOCR (local) | Only if Muse vision is too slow/costly |
| **Storage** | Temporary / local (Supabase optional later) | Keep minimal |
| **Deployment** | Local + ngrok / Vercel / Railway | Enough for demo |

**API Endpoint:** `https://api.meta.ai/v1` (provisional — confirm against official docs in Phase 0)  
**Authentication:** Meta Model API key, loaded from `backend/.env` as `META_API_KEY`. Never commit the key.  
**Repo layout (monorepo):**

```
dsc_hackathon/
├── Document_Screenshot_Cleaner_SAM_Hackathon_Plan.md
├── backend/        # FastAPI app
└── frontend/       # Next.js app
```

---

## 3. High-Level Architecture

```
User (Browser)
    ↓ Upload image
Next.js Frontend
    ↓ POST /api/process (multipart image)
FastAPI Backend
    ├── Call SAM 3.1 → boxes + masks
    ├── Extract text from regions (Muse vision by default)
    └── Call Muse → cleaned / proofread text
    ↓
Return JSON (boxes, overlay image, original text, cleaned text)
    ↓
Frontend displays side-by-side result
```

### 3.1 Backend API contract (pinned)

**`GET /api/health`** → `{ "status": "ok" }`

**`POST /api/process`** — multipart form, field `image` (JPEG/PNG, max 10 MB).
Response JSON:

```json
{
  "boxes": [{ "x": 0, "y": 0, "w": 100, "h": 50, "label": "text", "score": 0.97 }],
  "overlay_png_base64": "<base64-encoded PNG with masks drawn over original>",
  "original_text": "<raw extracted text>",
  "cleaned_text": "<Muse-proofread text>"
}
```

Design decision: the **backend pre-renders the overlay PNG**. The frontend only
displays it — no mask-decoding logic in the browser. If SAM mask parsing proves
slow during Phase 0/1, fall back to drawing **bounding boxes only** (same
contract, `overlay_png_base64` still returned).

### 3.2 Operational rules

- CORS: allow the local Next.js dev origin only.
- Upload limit: 10 MB; reject larger files with HTTP 413.
- Upstream timeout: 60 s per Meta API call; on timeout/failure return HTTP 502
  with a short error message shown in the UI.
- Missing `META_API_KEY`: backend refuses to start (fail fast with a clear log).

---

## 4. Phase-by-Phase Execution

### Phase 0: API Spike (first ~1 hour, before any scaffolding)
**Goal:** Prove the Meta Model API contract with a throwaway script.

**Execution steps:**
1. Confirm the exact SAM endpoint, auth header scheme, model ID (`sam-3.1`
   provisional), and the official SAM parser library name/version from docs.
2. Write `/tmp/sam_spike.py` (throwaway, not committed): send one real messy
   screenshot with a short noun-phrase prompt, print boxes/masks shape.
3. Same for one Muse text-cleanup call.
4. Record the verified request/response shapes; update §3.1/§5 if they differ.

**Done when:** One real image returns parseable boxes/masks AND one Muse call
returns cleaned text. If the spike fails, stop — do not scaffold around an
unverified API.

---

### Phase 1: Core Pipeline (Day 1)
**Goal:** Backend that accepts an image and returns masks + cleaned text.

**Execution steps:**
1. Scaffold FastAPI project under `backend/`; load `META_API_KEY` from `.env`.
2. Implement SAM 3.1 call using the Responses API:
   - Model: `sam-3.1` (verified in Phase 0)
   - Short noun-phrase prompts for objects the spike actually segments:
     `"stamp"`, `"signature"`, `"photograph"`, `"rectangle"`.
     Do not send `"text"`, `"document"`, or `"handwritten note"` — those
     returned zero matches in Phase 0.
3. Parse the response with `meta-sam-parser` (`image_segmentation_format`,
   `decode_mask_to_raster`). Paste each mask at the box origin, scaled to the box.
4. Extract text via **Muse vision full-image transcription** (Phase 0 finding:
   SAM does not segment text regions, so region-cropped OCR is out; transcribe
   the whole image, use SAM masks only for non-text overlays).
5. Send extracted text to Muse for proofreading and light cleanup.
6. Implement `POST /api/process` per the §3.1 contract + `GET /api/health`.
7. Apply §3.2 operational rules (CORS, 10 MB limit, 60 s timeout, fail-fast key).
8. Apply EXIF orientation, then cap the long edge at 2048 px. SAM, Muse, and
   the overlay all use that working image, so box coordinates match the PNG
   the client displays.

**Done when:** One real messy screenshot produces a valid response with boxes,
overlay PNG, and cleaned text. The automated suite covers the contract with a
mocked gateway. The live call still needs `META_API_KEY` in `backend/.env`.

---

### Phase 2: Minimal UI + End-to-End Demo (Day 2)
**Goal:** User can upload an image and see the result.

**Execution steps:**
1. Build a simple Next.js upload page under `frontend/`.
2. Display:
   - Original image
   - Image with SAM masks overlaid (from `overlay_png_base64`)
   - Cleaned / proofread text
3. Add basic loading and error states (including backend 502/413 messages).
4. Test with multiple sample images (chat screenshot, handwritten note, scanned form, mobile UI screenshot).
5. Record a 60–90 second demo video of the happy path.

**Done when:** Working web app + rough demo video exist.

---

### Phase 3: Polish + Optional Features (Day 3)
**Goal:** Make the demo look professional. Add extras only if Phase 2 is complete.

**Polish tasks:**
- Improve mask visualization (colors, transparency)
- Clean side-by-side layout
- Add copy / download for cleaned text
- Simple usage instructions on the page

**Optional features (maximum 1–2):**
- Flag uncertain or factual claims
- Basic noise / background removal using masks
- Export cleaned text as Markdown

**Done when:** Final demo video and submission materials are ready.

**Added after the demo:** the page shows the proofread edits against the transcription, checkboxes turn SAM regions on and off, and Try again resubmits the same file after a failed read. Later the page gained Cancel, region counts, and overlay PNG download. Fact-checking and mask-based background removal were not added. The demo videos predate these controls.

---

## 5. AI Models & Tools

| Tool | Role | Scoring Relevance |
|------|------|-------------------|
| **SAM 3.1** | Segment regions in uploaded images | High — primary Meta tooling |
| **Muse** (Spark / Wonder) | Proofread and clean extracted text | High — additional Meta tooling |
| **Meta Model API** | Serves both models | Required |
| **Official SAM Parser** | Decode boxes and masks | Recommended (avoid manual parsing) |
| **Muse Vision** | Extract text from regions (default) | Supporting |
| **EasyOCR** | Extract text from regions (fallback) | Supporting, only if needed |
| **Muse Code** | Assist in writing the application | Your existing plan |

**SAM prompting rules:**
- Use short concrete noun phrases only.
- One concept per API call.
- Do not send long instructions or questions.

**Verified IDs (Phase 0 spike, 21 Oct 2026):** endpoint `https://api.meta.ai/v1`,
`POST /responses`, auth `Authorization: Bearer $META_API_KEY`, model `sam-3.1`,
text models `muse-spark-1.3` / `muse-wonder-1.0` (bare `muse-spark` is NOT a valid
ID — returns 404). Image input: `input_image` content block with data URL.
**SAM must be called with `"stream": true`** — output arrives as special-token
text in `response.output_text.delta` events, one line per frame
(`<0f>id<|box;...|><|mask;...|>,...`), ending at `response.completed`.
Non-streaming calls return an empty message. Wire grammar: mask
`data=<H>,<W>,<enc>payload` (**height first**); mask `x,y` are always `0,0` —
paste the decoded mask at the **box origin** (`x1,y1`), scaled to box size.
Decode with `meta-sam-parser` (`pip install meta-sam-parser`):
`SegmentationMask(encoding, payload, width, height)` + `decode_mask_to_raster`.
**Key product finding:** text-oriented prompts (`"text"`, `"document"`,
`"printed text"`, `"receipt"`, `"logo"`, …) return **zero matches** on both
synthetic and real document images. SAM segments concrete visual objects only
(stamps, signatures-as-graphics, logos, photos, rectangles all hit). Consequence:
text extraction comes from **Muse vision full-image transcription** (verified:
perfect receipt transcription), SAM covers non-text regions (stamps, signatures,
graphics, noise). The `§3.1` contract is unchanged — boxes + overlay PNG.

### 5.1 F0 spike results (Feature Expansion Plan, 23 Oct 2026)

**Set:** 8 generated documents, made for this run with known ground truth:
invoice, receipt, signed form, ID card on a desk, handwritten note, chat
screenshot, letter, bank slip. Seven are shot as photos (tilt, background,
uneven light, noise, 2200–2400 px); the chat is a flat 1170×2532 screenshot.
Everything goes through `prepare_image` (2048 px cap), as in production.
Signatures are drawn strokes, faces are drawn portraits, and handwriting is an
italic font with jitter. **No real photos were used.** Wikimedia is blocked
from the dev container, so every result below needs a recheck on real
photos. That recheck matters most for S1 and S4. About 250 live calls in
total. The scripts and images stay in the scratchpad and are not committed.

**S1 — SAM prompts** (13 prompts × 8 images, plus a follow-up on 5 images)

| Prompt | Targets found | Extra regions | Notes |
|---|---|---|---|
| `stamp` | 4/4 | 0 | round and rectangular |
| `seal` | 3/4 | 0 | missed the rectangular bank stamp |
| `logo` | 3/3 | 3 | finds the logo mark, not the wordmark beside it. The 3 extra regions are round stamps |
| `qr code` | 1/1 | 0 | |
| `barcode` | 2/2 | 0 | |
| `face` | 3/3 portraits | 0 | |
| `checkbox` | 5/5 | 0 | ticked and empty |
| `table` | 2/3 | 0 | missed the small two-row table |
| `id card` | 1/1 | 2 | the extras are whole invoice and receipt pages |
| `photograph` | 0/3 | 0 | `photo`, `person` and `headshot` found the portrait on both images tried |
| `signature` | 0/4 | 0 | also 0 for `handwritten signature`, `autograph`, `scribble`, on tight crops, on a cursive-name signature, and on a plain black stroke |
| `handwriting` | 0/5 | 0 | also 0 for `handwritten text` |
| `rectangle` | — | 14 | not scored: chat bubbles, the card, table blocks |

The `logo` note in the Phase 0 block above is out of date: `logo` now hits.

**S2 — JSON from Muse** (`muse-spark-1.3`, 10 runs per mode)

| Mode | Strict parse | Matches the F3 schema | Field values found in the transcript |
|---|---|---|---|
| Responses `text.format` JSON schema (`strict: true`) | 10/10 | 10/10 | 148/148 |
| Prompt "return only JSON" | 10/10 | 10/10 | 138/138 |

Document type was right on 9/10. The bank slip came back as `receipt`.

**S3 — sensitive text spans** (`text.format` schema, categories as an enum)
- 42 items returned, all verbatim substrings of the transcript.
- Precision is 39/42 = **93%**. The 3 misses are business addresses (shop and
  firm letterheads). Names outside the ground truth (a cashier, a checker,
  "Sam", "Ana", the letter's signer) and a sort code count as correct.
- Recall is 33/34 ground-truth items. The miss is the receipt's
  already-masked card number `**** 4242`.

**S4 — word boxes from Muse vision** (3 strings per image, 24 total; pixel coordinates)

| Model | IoU ≥ 0.5 | Box fully covers the word: as returned / +0.5 h / +0.75 h | Median / max time |
|---|---|---|---|
| `muse-spark-1.3` | 13/24 | 4 / 17 / 21 | 4.6 s / 6.0 s |
| `muse-wonder-1.0` | 21/24 | 7 / 22 / **24** | 15.3 s / 46.3 s |

Boxes are in pixels. Neither 0–1000 nor 0–1 scaling matched anything. Spark
put two receipt boxes on the wrong line. Wonder's boxes sit a few pixels off
the word, so they need a margin before they can hide it.

**S5 — region descriptions** (11 SAM crops, `muse-spark-1.3`)
- 11/11 are accurate and quote the text inside, for example *Circular red
  stamp: "PAID" "NORTHWIND STUDIO LEEDS"*.
- No guesses about identity.
- Two crops carried a wrong SAM label: a stamp tagged `logo` and a page tagged
  `id card`. The description named what was really there both times.

**S6 — latency and size** (4 calls in flight)

| Call | Median | p90 | Max |
|---|---|---|---|
| SAM (178 calls) | 1.4 s | 3.9 s | 11.3 s |
| Transcribe | 4.7 s | 6.4 s | 7.9 s |
| Proofread | 2.9 s | 3.7 s | 4.8 s |
| Extract (schema) | 5.6 s | 6.1 s | 6.3 s |
| Sensitive spans | 7.8 s | 12.2 s | 16.5 s |
| Describe region | 3.8 s | 6.0 s | 6.7 s |
| Word boxes (wonder) | 15.3 s | 36.9 s | 46.3 s |

The overlay PNG at 2048 px is 0.39–2.30 MB (median about 1.6 MB). As JPEG q85
the same overlay is 0.13–0.26 MB. No call failed.

**Decisions**

| Gate | Decision |
|---|---|
| S1 | Suggestion chips: Logo, QR code, Barcode, Face, Table, Checkbox, Seal. `id card` is allowed but not suggested. `handwriting` and `handwritten text` join the blocklist with the friendly message. |
| S1, presets | `photograph` finds nothing; `photo` does. Change the preset prompt to `photo` and keep the label "Photograph". **`signature` is open:** it found nothing on any generated image. F1 hides signatures by default, so it has to be checked on real signed pages before F1a is built around it. If it still finds nothing, the fallback is a Muse vision box for the signature, which needs its own check. |
| S2 | Use `text.format` with a strict JSON schema. Keep strict parsing, the schema check and the single repair attempt as a safety net. |
| S3 | 93% ≥ 90% → **ship F1b** with model spans plus the regex backstop. Add "only private people's details, not business addresses" to the prompt. |
| S4 | Passes at 24/24 with `muse-wonder-1.0` and a margin of 0.75 × box height. **F1c ships behind `REDACT_IMAGE_TEXT`, off by default**, until it passes on real photos. Spark is not used for boxes. |
| S5 | **Ship F5.** Show the description next to SAM's label, because it corrects wrong labels. |
| S6 | Keep the 60 s per-call timeout and the 150 s request budget. The worst chain (transcribe → spans → wonder boxes) is about 70 s. Overlay PNGs are under the 3 MB threshold, so **keep PNG for both images** (§5.4 of the expansion plan) and measure again on real photos, which compress worse. |

---

## 6. Submission Checklist

- [x] Core upload → result flow works
- [x] 60–90 second demo video recorded
- [x] Clear mention of SAM 3.1 + Muse usage
- [ ] Project hosted or GitHub link ready
- [ ] Submitted on Cerebral Valley portal before **4 November, 9:00 PM ET**
- [ ] Official hackathon rules accepted (when published)

### Phase status tracker

Update `Status` as work progresses. Allowed values: `Not Started` →
`In Progress` → `Done`. Use `Blocked` plus a note naming the blocker.
`Tests` / `Docs` / `Commit` flip to `Yes` when that phase delivers them.

| Phase | Work item | Ref | Status | Tests | Docs | Commit | Notes |
|-------|-----------|-----|--------|-------|------|--------|-------|
| 0 | API spike: verify SAM + Muse contract | §4 Phase 0, §9 Q1–Q3 | Done | No | No | No | Contract verified on real images; scripts in /tmp, not committed |
| 1 | Backend pipeline: `/api/process` + overlay | §4 Phase 1, §3.1 | Done | Yes | Yes | Yes | Mocked contract tests pass. Live Meta call confirmed in Phase 2. Concepts: stamp, signature, photograph, rectangle. |
| 2 | Next.js upload page + rough demo video | §4 Phase 2 | Done | Yes | Yes | Yes | Chrome against the live API: invoice, handwritten note, chat, mobile UI. Demo is `demo/happy-path.webm` (77s). Deploy stays local. |
| 3 | Polish, README, final video + submission | §4 Phase 3, §6 | Done | Yes | Yes | Yes | Lighter rectangle masks, usage steps, copy, and Markdown download. Final demo is `demo/final-demo.webm` (67s). Fact-checking and background removal were not added. Portal submission is still open. |
| 3b | Proofread diff, region toggles, retry | Added after §4 Phase 3 | Done | Yes | Yes | Yes | Page shows transcription against proofread text. `concepts` selects stamp, signature, photograph, rectangle. Try again sends a new request. |
| 3c | Hardening and presentation | Added after 3b | Done | Yes | Yes | Yes | Faster mask drawing, boxes clipped to the image, fenced proofread prompt, optional per-IP rate limit, model names in the response. Page: Cancel, 150 s timeout, region counts with best score, overlay PNG download. CI workflow, MIT license, README diagram and screenshot. |
| 4 | Feature expansion F0–F8 | `Feature_Expansion_Plan.md` §13 | Done | Yes | Yes | Yes | F0–F8 (share-safe copy, custom regions, extraction, demo UX and browser tests, live progress, region descriptions, ask the document, read aloud), the request budget, server feature switches, a live smoke script, and deploy configs with a guide (`docs/DEPLOY.md`). Merged to `main` in vignarajj/dsc_hackathon#1. Per-item history lives in the expansion plan's tracker. |
| 5 | Launch: live checks, deploy, demo, submit | `docs/LAUNCH.md` | In Progress | No | Yes | Yes | Merge done. A live run on the four generated samples (40 calls) passed: 4 of 4 types right, 20 of 20 drawn-in personal details hidden. Real-photo checks, deploy, demo, and submission remain. |

---

## 7. Constraints & Risk Controls

- No authentication, user accounts, or history in the MVP.
- No multi-page document support in the first version.
- Do not start fact-checking or web search until the core demo is working.
- If SAM mask parsing is slow, fall back to bounding boxes for the first demo.
- Record the demo video as soon as the happy path works.
- Backend pre-renders the overlay; frontend does no mask decoding (§3.1).
- 10 MB upload cap, 60 s upstream timeout, fail-fast on missing API key (§3.2).
- No scaffolding before the Phase 0 spike verifies the API contract.

---

## 8. Immediate Next Steps

1. The page shows proofread edits, region checkboxes, Try again, Cancel, region counts, and overlay download. The demo videos predate those controls. The repo is still private.
2. Make the repo public, or invite the judges, before you rely on the GitHub link.
3. Submit on the Cerebral Valley portal yourself. Deploy stays local unless the demo needs a public URL.

---

## 9. Open Questions (resolve in Phase 0)

1. ~~Exact SAM endpoint path, auth header scheme, and model ID~~ — resolved, see §5.
2. ~~Official SAM parser library~~ — resolved: `meta-sam-parser` 0.1.0. Streaming special-token text, not plain JSON. See §5.
3. ~~Billing~~ — resolved: payment method added, spike verified end to end.

---

*Core first. Demo second. Extra features only if time remains.*
