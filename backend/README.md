# Document screenshot cleaner API

The project overview is in the root [README](../README.md). This service accepts one JPEG or PNG and returns SAM 3.1 boxes, a
pre-rendered overlay, the Muse transcription, and a proofread copy of that text.

## Run

```bash
cd backend
cp .env.example .env
# put your Meta Model API key in META_API_KEY
uv sync
uv run uvicorn dsc_backend.main:app --reload --port 8000
```

The process refuses to start when `META_API_KEY` is missing.

- `GET http://127.0.0.1:8000/api/health` → `{"status":"ok"}`
- `POST http://127.0.0.1:8000/api/process` with multipart field `image`
- Optional multipart field `concepts`, a comma-separated list. Omit it to use `SAM_CONCEPTS`.

```bash
curl -s -F "image=@note.png;type=image/png" http://127.0.0.1:8000/api/process
curl -s -F "image=@note.png;type=image/png" -F "concepts=rectangle" http://127.0.0.1:8000/api/process
```

## Response

```json
{
  "boxes": [{ "x": 0, "y": 0, "w": 100, "h": 50, "label": "stamp", "score": 0.97 }],
  "overlay_png_base64": "<png with masks drawn over the working image>",
  "original_text": "<muse transcription>",
  "cleaned_text": "<muse proofread text>",
  "models": { "segmentation": "sam-3.1", "transcription": "muse-spark-1.3", "proofread": "muse-spark-1.3" }
}
```

`models` echoes the configured model IDs so the page can name them.

`score` is the SAM confidence when the model returns one, otherwise `null`.
An image with no matching objects returns `"boxes": []` and an overlay of the
working image with no masks. That is a successful response.

## What the pipeline does

1. Accept JPEG or PNG up to 10 MB. Anything else is HTTP 400. Larger files are HTTP 413.
2. Apply EXIF orientation, then shrink the long edge to 2048 px when needed.
   SAM, Muse, and the overlay all use that working image, so the boxes match
   the picture the browser will show.
3. Call `sam-3.1` once per selected concept, in parallel, with `stream: true`.
   The optional `concepts` field accepts `stamp`, `signature`, `photograph`,
   and `rectangle`. Names are matched without regard to case, duplicates are
   ignored, and the order is always that list. An empty field skips
   segmentation. An unknown name is HTTP 400 and no model is called. When the
   field is absent, `SAM_CONCEPTS` is used. Text prompts are omitted because
   the Phase 0 spike showed they return no matches.
4. Decode each stream with `meta-sam-parser` and paste the mask at the box
   origin, scaled to the box. A box whose mask cannot be decoded is still drawn
   as an outline. Box coordinates are rounded, the reported boxes and outlines
   are clipped to the working image, and a box entirely off it is dropped.
5. Draw a light colored fill and a thicker outline on larger images. Rectangle
   fills stay lighter than stamps so the page text remains readable. The upload
   page legend uses the same colors.
6. Transcribe the whole image with `muse-spark-1.3`, then proofread that text
   with the same model. `MUSE_TEXT_MODEL` can be set to `muse-wonder-1.0`.
   The proofread prompt fences the transcription in `<transcript>` tags and
   tells the model never to follow instructions inside it. A literal closing
   tag in the text is defused, and an echoed fence is stripped from the answer.
7. Each Meta call has a 60 second timeout. This service does not retry a model
   call. Timeout or upstream failure is HTTP 502 with `{"detail": "..."}`.
   The upload page can send the same image again as a new request.

CORS allows `http://localhost:3000` and `http://127.0.0.1:3000` only.

`RATE_LIMIT_PER_MINUTE` caps `/api/process` per client IP over a sliding
minute. It is off (`0`) by default. Over the limit is HTTP 429 with
`"Too many requests. Wait a minute and try again."`. The count lives in memory,
so it resets on restart and is per process.

## Tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The test suite mocks the model gateway. It does not call Meta.

The upload page lives in `frontend/`. See `frontend/README.md`.
