# Document screenshot cleaner UI

Upload page for the Phase 1 API. It posts the image to `POST /api/process` and shows the original, the SAM overlay, and the cleaned text.

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

The page lists the steps, shows the original beside the SAM overlay, and names the mask colors. Copy puts the cleaned text on the clipboard. Download saves `<name>.cleaned.md`.

A 67 second recording of the polished page is at `../demo/final-demo.webm`. The earlier happy path is at `../demo/happy-path.webm`.

## Tests

```bash
pnpm test
pnpm lint
```
