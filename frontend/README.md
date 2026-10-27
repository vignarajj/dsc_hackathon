# Document screenshot cleaner UI

Upload page for the API. The project overview is in the root [README](../README.md). This page posts the image to `POST /api/process` and shows the result in four tabs: the regions, the text, the document data, and a share-safe copy.

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

JPEG and PNG only, up to 10 MB. A backend 413, 429, or 502 message is shown on the page. A request can take up to a minute. Cancel returns the page to its idle state and closes the progress stream, which makes the API stop the request. The page gives up after 180 seconds and offers Try again.

The page lists four steps. Four region checkboxes start checked. The page sends that selection as the `concepts` field. Changing the boxes after a result does not send another request; clean again to apply it. Unchecking every region still transcribes the page and returns an overlay with no masks.

Below the four region checkboxes, Find something else adds up to 3 more things for SAM to look for. Type a name and press Enter or Add, or pick a suggestion (Logo, QR code, Barcode, Face, Table, Checkbox, Seal; the ones SAM found in the F0 spike). The page checks the name the same way the API does: 1 to 3 plain words, no text prompts such as "receipt", and no repeats. Typing a preset name such as "stamp" turns that preset on. Each added region shows its color and a remove button, is sent in the `custom` field, and can be hidden in the share-safe copy. The legend under the result uses the colors the API returns, so it matches the overlay.

Under the region checkboxes, the share-safe options choose which marked regions to hide (Signature and Photograph start checked, Stamp does not), whether to hide them with a black box or a blur, and whether to mask personal details in the text (on by default). A region that is not marked cannot be hidden, so its box is turned off. The page sends these as `redact`, `redact_style`, and `redact_text`. Changing any of them after a result asks you to clean again.

The Share-safe tab shows the hidden copy under a slider: the original is left of the handle and the share-safe copy right of it. Download share-safe image saves `<name>.safe.png`, which has no location or camera data. The panel says whether text inside the picture was hidden too; by default it is not, and the page says to share the text version for that. Below it, the shareable text has each personal detail replaced by its category, such as `[PHONE]`, with Copy shareable text, and each detail found is listed with its category. Notes from the API, such as a region that was not found, appear in a quiet list above the result.

Describe each region in a few words is off by default, since it adds up to 8 Muse calls. When on, the page sends `describe=true`, and the Overview tab lists a note for each region described. Pointing at or focusing a note outlines that one box on the picture with the note beside it, placed toward the middle of the picture so the frame does not cut it off.

On load, the page asks `GET /api/config` which optional features the server runs. An option the server has turned off is disabled and marked "turned off on this server", and is sent as `false`. When the Muse check for personal details is off, the text option stays on and says that only phone numbers, emails, and account numbers will be masked. If the server does not answer, the page assumes everything is on.

Pull out the document type and key fields is on by default and sends `extract=true`. The Data tab shows the type, a title, a one-line summary, and a table of fields with a Copy button per row. A value the API could not find in the transcription or the proofread is marked "not found in text". Download JSON saves `<name>.data.json` with the fields, the regions, and both texts. Download CSV saves `<name>.data.csv` with `label,value` rows; every value is quoted, and a value starting with `=`, `+`, `-`, or `@` gets a leading `'` so a spreadsheet does not run it as a formula.

In the Overview tab, each region that was requested shows how many boxes came back and the best confidence score. Download overlay PNG saves the overlay as `<name>.overlay.png`. When the API sends model names, the tab prints them under the regions.

When the proofread differs from the transcription, struck-through words were in the transcription and underlined words are the proofread wording. When they match, the page says "No wording changes." Copy puts the proofread text on the clipboard. Download saves `<name>.cleaned.md` from that same text. Both stay off when the proofread text is empty, even if the transcription is still on screen.

If the read fails and the file is still selected, Try again sends that file once more with the regions currently checked. A file the page rejects, such as a GIF or a file over 10 MB, is cleared, so Try again is not offered. The API does not retry a model call by itself.

A 67 second recording of the polished page is at `../demo/final-demo.webm`. The earlier happy path is at `../demo/happy-path.webm`. Both were recorded before the region checkboxes, the proofread comparison, Try again, Cancel, region counts, overlay download, and everything in the feature expansion plan.

## Read aloud

Read aloud sits beside Copy and Download in the Text tab. It reads the proofread text with the browser's own speech, so it makes no API call. The text is spoken in sentence-sized pieces, because Chrome stops a long utterance part way through. While it speaks, the button reads Stop reading. Speech stops when the text changes or the tab goes away. The button is not shown in a browser without speech. The page sets no language for the voice, since the API does not report the document's language, so the browser's default voice is used.

## Ask the document

Under the text comparison in the Text tab, Ask the document sends a question to `POST /api/ask` with the proofread text and any extracted fields. The image is not sent again. Three suggested questions match the document type, such as "What is the total due?" for an invoice, with general ones when the type is unknown. Each answer is listed newest first under its question. When Muse points to the exact words, they are shown as a quote from the page; a quote that is not really in the text is never shown. A question the page cannot answer gets "The document does not say." Questions are limited to 300 characters, and the page sends at most the first 20,000 characters of text.

## Progress

The page asks the API to stream its progress. While a request runs, a list under the progress bar shows each step the API planned (preparing the image, finding regions with SAM, reading the text with Muse, proofreading, and, when chosen, describing each region, pulling out fields, and finding personal details, then building the overlay and share-safe copy). Each step is marked waiting, in progress, or done, with a short detail such as how many of each region were found. Cancel closes the stream, and the API then stops the request instead of finishing it. An API that does not stream still works: the page reads its plain JSON answer and shows no step list.

## Layout

No file to hand? Four sample pages sit under the drop zone: an invoice with a PAID stamp, a signed form with a photo, a handwritten note, and a chat screenshot. They live in `public/samples/` and were made for this app; the names are invented and the phone numbers are from reserved drama ranges. Clicking one loads it as a file, so it goes through the same checks and request as an upload.

A result opens in four tabs. The arrow keys move between tabs, and Home and End jump to the first and last. Overview shows the original and the SAM overlay under one slider (original left of the handle) and lists each region that was requested. Pointing at a region, or focusing it with the keyboard, outlines its boxes on the picture. Text holds the transcription and proofread comparison, Read aloud, and Ask the document. Data holds the document fields. Share-safe holds the hidden copy and the shareable text. A tab with nothing to show says why and how to fill it. Notes from the API sit above the tabs.

The result code is in `src/app/results/`: one file per tab, plus the tabs, the slider, and the region labels and colors.

## Tests

```bash
pnpm test        # unit tests in src/lib/*.test.ts, with Node's test runner
pnpm lint
pnpm typecheck   # generates Next route types, then runs tsc
pnpm test:e2e     # browser tests, see below
```

`pnpm test:e2e` builds the page into `.next-e2e` against a fake API and runs Playwright on desktop and on a 375 px dark-mode phone. The fake API is `backend/tests/fake_server.py`: the real FastAPI app with a fixed model gateway, so the tests never call Meta and need no key. It starts its own servers on ports 8100 and 3100 and never reuses one that is already running. The fake API pauses one second in the proofread so the tests can see a step in progress. The tests walk a sample through every tab, check that each download produces a file, check the step list and cancelling a streamed run, ask the document a question, check read aloud (with recorded speech, since headless Chromium has no voices) and its absence without speech, check options the server has turned off, and cover region notes, the tab keys, the region highlight, empty tabs, Cancel, and a blocked custom region. Install a browser once with `pnpm exec playwright install chromium`, or set `CHROMIUM_PATH` to one already installed. CI runs the same tests.
