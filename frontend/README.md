# Document screenshot cleaner UI

Upload page for the API. The project overview is in the root [README](../README.md). This page posts the image to `POST /api/process` and shows the original, the SAM overlay, and the cleaned text.

## Run

Start the API first, from `backend/`:

```bash
cp .env.example .env
# set META_API_KEY
uv sync
uv run uvicorn dsc_backend.main:app --reload --port 8000
```

Then, from `frontend/`:

```bash
pnpm install
pnpm dev
```

Open http://localhost:3000. The page calls `http://127.0.0.1:8000` unless `NEXT_PUBLIC_API_BASE_URL` is set. Copy `.env.example` to `.env.local` to change it.

JPEG and PNG only, up to 10 MB. A backend 413 or 502 message is shown on the page. A request can take up to a minute.

The page lists the steps, shows the original beside the SAM overlay, and names the mask colors. Four region checkboxes start checked. The page sends that selection as the `concepts` field. Changing the boxes after a result does not send another request; clean again to apply it. Unchecking every region still transcribes the page and returns an overlay with no masks.

When the proofread differs from the transcription, struck-through words were in the transcription and underlined words are the proofread wording. When they match, the page says "No wording changes." Copy puts the proofread text on the clipboard. Download saves `<name>.cleaned.md` from that same text. Both stay off when the proofread text is empty, even if the transcription is still on screen.

If the read fails and the file is still selected, Try again sends that file once more with the regions currently checked. A file the page rejects, such as a GIF or a file over 10 MB, is cleared, so Try again is not offered. The API does not retry a model call by itself.

A 67 second recording of the polished page is at `../demo/final-demo.webm`. The earlier happy path is at `../demo/happy-path.webm`. Both were recorded before the region checkboxes, the proofread comparison, and Try again.

## Tests

```bash
pnpm test
pnpm lint
```
