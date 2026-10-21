# Document screenshot cleaner

Upload one screenshot. SAM 3.1 marks stamps, signatures, photographs, and rectangles. Muse Spark transcribes the page and proofreads the text. The page shows the original, the overlay, and the cleaned text, and it can copy or download that text as Markdown.

## Run

From `backend/`:

```bash
cp .env.example .env
# set META_API_KEY
uv sync
uv run uvicorn dsc_backend.main:app --reload --port 8000
```

From `frontend/`:

```bash
pnpm install
pnpm dev
```

Open http://localhost:3000. The page calls http://127.0.0.1:8000 unless `NEXT_PUBLIC_API_BASE_URL` is set.

JPEG or PNG, up to 10 MB, one image at a time. `backend/.env` stays off GitHub.

## Demo

- `demo/final-demo.webm` is the polished walkthrough.
- `demo/happy-path.webm` is the earlier rough recording.

## Checks

```bash
cd backend && uv run pytest
cd frontend && pnpm test && pnpm lint
```
