# Document screenshot cleaner

Upload one screenshot or photo of a page. The app marks stamps, signatures, photographs, and rectangles, transcribes the visible text, and proofreads it. You get the original picture, a colored overlay, and the cleaned text. You can copy that text or download it as Markdown.

This is a small tool for a messy real-world image: a photographed form, a handwritten note, a chat, or a phone screen. It was built for the Meta Global AI Developer Hackathon, Indie track, on the theme Build for Your World.

## What you can do

1. Choose a JPEG or PNG up to 10 MB.
2. Wait while the image is read. A request can take up to a minute.
3. Compare the original with the overlay. Each kind of region has its own color.
4. Copy the cleaned text, or download `<name>.cleaned.md`.

An image with no matching regions is still a success. The overlay is the picture with no masks, and the text is whatever was read from the page. If the page has no text, the screen says so and the copy and download buttons stay off.

## What is in this repo

| Path | What it is |
|---|---|
| `backend/` | FastAPI service. Accepts the image, calls the models, and draws the overlay. |
| `frontend/` | Next.js page. Uploads the image and shows the result. |
| `demo/final-demo.webm` | 67 second walkthrough of the polished page. |
| `demo/happy-path.webm` | 77 second earlier recording of the first working page. |
| `Document_Screenshot_Cleaner_SAM_Hackathon_Plan.md` | The execution plan and phase tracker. |

There is no account system, no saved history, and no multi-page document support.

## How one upload is handled

The browser sends the file to `POST /api/process`. The API does not trust the browser to draw masks.

1. It accepts only JPEG or PNG, up to 10 MB. Anything else is HTTP 400. A larger file is HTTP 413.
2. It applies EXIF orientation, then shrinks the long edge to 2048 px when needed. Segmentation, transcription, and the overlay all use that same working image, so the boxes line up with the picture on the page.
3. It asks SAM 3.1, in parallel, for `stamp`, `signature`, `photograph`, and `rectangle`. Prompts for text, a document, or a handwritten note are not sent. Those returned no regions in the early spike. Text comes from a full-image transcription, not from the regions.
4. It decodes each SAM stream with `meta-sam-parser` and paints the mask at the box. A box whose mask cannot be decoded is still outlined. Rectangle fills are lighter than stamps so the words underneath stay readable.
5. It transcribes the whole image with Muse Spark (`muse-spark-1.3`), then proofreads that text with the same model. An empty transcription is not proofread.
6. Each model call has a 60 second timeout and is not retried. A timeout or an upstream failure is HTTP 502 with a short `detail` string, and the page shows that string.

The response looks like this:

```json
{
  "boxes": [{ "x": 0, "y": 0, "w": 100, "h": 50, "label": "stamp", "score": 0.97 }],
  "overlay_png_base64": "<png with the masks drawn on the working image>",
  "original_text": "<transcription>",
  "cleaned_text": "<proofread text>"
}
```

`score` is the model's confidence when it sends one, otherwise `null`. `GET /api/health` returns `{ "status": "ok" }`.

## Requirements

- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- Node.js and pnpm 11
- A Meta Model API key

The key belongs in `backend/.env` only. That file is gitignored.

## Run it locally

From `backend/`:

```bash
cp .env.example .env
# set META_API_KEY
uv sync
uv run uvicorn dsc_backend.main:app --reload --port 8000
```

The process exits on startup if `META_API_KEY` is missing.

From `frontend/`:

```bash
pnpm install
pnpm dev
```

Open http://localhost:3000. The page calls http://127.0.0.1:8000 unless you set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local`. Copy `frontend/.env.example` to change it.

Check the API on its own:

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s -F "image=@note.png;type=image/png" http://127.0.0.1:8000/api/process
```

## Configuration

Optional values in `backend/.env`:

| Name | Default |
|---|---|
| `META_BASE_URL` | `https://api.meta.ai/v1` |
| `SAM_MODEL` | `sam-3.1` |
| `MUSE_VISION_MODEL` | `muse-spark-1.3` |
| `MUSE_TEXT_MODEL` | `muse-spark-1.3` |
| `SAM_CONCEPTS` | `stamp,signature,photograph,rectangle` |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` |
| `UPSTREAM_TIMEOUT_SECONDS` | `60` |

`MUSE_TEXT_MODEL` can be set to `muse-wonder-1.0` for the proofread step. The vision step stays on Muse Spark.

## Checks

```bash
cd backend && uv run pytest
cd frontend && pnpm test && pnpm lint
```

Backend tests use a stand-in model client, so they do not spend API credit. The frontend tests cover file checks, error messages, and the Markdown filename. A browser pass of the running app is separate and needs the key.

## Hosting

Nothing in this repo is deployed. Both processes are meant to run on your machine.

A public test needs the API and the page on hosts that can hold a request for about a minute. Put `META_API_KEY` in the API host's environment, not in git. Set `CORS_ORIGINS` to the page's origin, and set `NEXT_PUBLIC_API_BASE_URL` to the API's public URL. The API has no login. Anyone who can reach a public copy can spend the Meta key, so do not leave that URL open.

## More detail

- `backend/README.md` — request rules and the pipeline
- `frontend/README.md` — the upload page
- `Document_Screenshot_Cleaner_SAM_Hackathon_Plan.md` — scope and phase status
