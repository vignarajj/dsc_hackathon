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

JPEG and PNG only, up to 10 MB. A backend 413, 429, or 502 message is shown on the page. A request can take up to a minute. Cancel stops waiting and returns the page to its idle state; a model call already under way still finishes on the server. The page gives up after 180 seconds and offers Try again.

The page lists the steps, shows the original beside the SAM overlay, and names the mask colors. Four region checkboxes start checked. The page sends that selection as the `concepts` field. Changing the boxes after a result does not send another request; clean again to apply it. Unchecking every region still transcribes the page and returns an overlay with no masks.

Below the four region checkboxes, Find something else adds up to 3 more things for SAM to look for. Type a name and press Enter or Add, or pick a suggestion (Logo, QR code, Barcode, Face, Table, Checkbox, Seal; the ones SAM found in the F0 spike). The page checks the name the same way the API does: 1 to 3 plain words, no text prompts such as "receipt", and no repeats. Typing a preset name such as "stamp" turns that preset on. Each added region shows its color and a remove button, is sent in the `custom` field, and can be hidden in the share-safe copy. The legend under the result uses the colors the API returns, so it matches the overlay.

Under the region checkboxes, the share-safe options choose which marked regions to hide (Signature and Photograph start checked, Stamp does not), whether to hide them with a black box or a blur, and whether to mask personal details in the text (on by default). A region that is not marked cannot be hidden, so its box is turned off. The page sends these as `redact`, `redact_style`, and `redact_text`. Changing any of them after a result asks you to clean again.

The Share-safe copy panel shows the hidden copy under a slider: the original is left of the handle and the share-safe copy right of it. Download share-safe image saves `<name>.safe.png`, which has no location or camera data. The panel says whether text inside the picture was hidden too; by default it is not, and the page says to share the text version for that. Below it, the shareable text has each personal detail replaced by its category, such as `[PHONE]`, with Copy shareable text, and each detail found is listed with its category. Notes from the API, such as a region that was not found, appear in a quiet list above the result.

Under the pictures, each region that was requested shows how many boxes came back and the best confidence score. Download PNG saves the overlay as `<name>.overlay.png`. When the API sends model names, the page prints them under the result.

When the proofread differs from the transcription, struck-through words were in the transcription and underlined words are the proofread wording. When they match, the page says "No wording changes." Copy puts the proofread text on the clipboard. Download saves `<name>.cleaned.md` from that same text. Both stay off when the proofread text is empty, even if the transcription is still on screen.

If the read fails and the file is still selected, Try again sends that file once more with the regions currently checked. A file the page rejects, such as a GIF or a file over 10 MB, is cleared, so Try again is not offered. The API does not retry a model call by itself.

A 67 second recording of the polished page is at `../demo/final-demo.webm`. The earlier happy path is at `../demo/happy-path.webm`. Both were recorded before the region checkboxes, the proofread comparison, Try again, Cancel, region counts, and overlay download.

## Tests

```bash
pnpm test
pnpm lint
pnpm typecheck   # generates Next route types, then runs tsc
```
