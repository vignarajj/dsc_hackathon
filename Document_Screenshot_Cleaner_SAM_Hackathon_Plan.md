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

---

## 6. Submission Checklist

- [x] Core upload → result flow works
- [x] 60–90 second demo video recorded
- [ ] Clear mention of SAM 3.1 + Muse usage
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
| 3 | Polish, README, final video + submission | §4 Phase 3, §6 | Not Started | No | No | No | Max 1–2 extras |

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

1. Phase 3 polish is next: copy and download, usage instructions, and a cleaner layout. Pick at most one or two extras.
2. Push the demo commit yourself. The GitHub repo is private, so judges cannot open it until it is public or they are invited.
3. Deploy target is still local. Pick Vercel and Railway only if the demo needs a public URL.

---

## 9. Open Questions (resolve in Phase 0)

1. ~~Exact SAM endpoint path, auth header scheme, and model ID~~ — resolved, see §5.
2. ~~Official SAM parser library~~ — resolved: `meta-sam-parser` 0.1.0. Streaming special-token text, not plain JSON. See §5.
3. ~~Billing~~ — resolved: payment method added, spike verified end to end.

---

*Core first. Demo second. Extra features only if time remains.*
