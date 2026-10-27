# Document screenshot cleaner API

The project overview is in the root [README](../README.md). This service accepts one JPEG or PNG
and returns SAM 3.1 boxes, a pre-rendered overlay, the Muse transcription and proofread, and, on
request, a share-safe copy, masked text, key fields, and region descriptions. It can stream its
progress, and it answers questions about a page's text.

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
- `GET http://127.0.0.1:8000/api/config` → which optional features this server runs; see
  [Feature switches](#feature-switches)
- `POST http://127.0.0.1:8000/api/ask` with a JSON question; see [Ask the document](#ask-the-document)
- `POST http://127.0.0.1:8000/api/process` with multipart field `image`
- Optional multipart field `concepts`, a comma-separated list. Omit it to use `SAM_CONCEPTS`.
- Optional multipart field `custom`: up to 3 more things for SAM to find, comma-separated,
  such as `logo,qr code`.
- Optional multipart field `redact`, a comma-separated list of marked regions to hide
  in a share-safe copy. Omit it for no copy.
- Optional multipart field `redact_style`: `black` (default) or `blur`.
- Optional multipart field `redact_text`: `true` to find personal details in the text and
  return a masked copy. Default `false`.
- Optional multipart field `extract`: `true` to return the document type, a summary, and key
  fields. Default `false`.
- Optional multipart field `describe`: `true` to add a short Muse description to each region.
  Default `false`.
- Optional header `Accept: application/x-ndjson` to stream progress; see
  [Live progress](#live-progress).

```bash
curl -s -F "image=@note.png;type=image/png" http://127.0.0.1:8000/api/process
curl -s -F "image=@note.png;type=image/png" -F "concepts=rectangle" http://127.0.0.1:8000/api/process
curl -s -F "image=@form.jpg;type=image/jpeg" -F "redact=signature,photograph" http://127.0.0.1:8000/api/process
```

## Response

```json
{
  "boxes": [
    {
      "x": 0, "y": 0, "w": 100, "h": 50, "label": "stamp", "score": 0.97,
      "description": "Round red stamp reading \"PAID\""
    }
  ],
  "overlay_png_base64": "<png with masks drawn over the working image>",
  "original_text": "<muse transcription>",
  "cleaned_text": "<muse proofread text>",
  "models": {
    "segmentation": "sam-3.1",
    "transcription": "muse-spark-1.3",
    "proofread": "muse-spark-1.3",
    "signatures": "muse-spark-1.3"
  },
  "palette": { "stamp": "#dc2626", "logo": "#7c3aed" },
  "redacted_png_base64": "<png with the chosen regions hidden, or null>",
  "sensitive": [
    { "category": "phone", "text": "07911 123456", "source": "pattern" },
    { "category": "name", "text": "Marco Bellini", "source": "model" }
  ],
  "shareable_text": "His name is [NAME], call [PHONE].",
  "image_text_hidden": false,
  "document": {
    "type": "invoice",
    "title": "Invoice INV-2041",
    "summary": "Invoice from Northwind Studio, $1,200.00 due.",
    "fields": [{ "label": "Total due", "value": "$1,200.00", "found_in_text": true }]
  },
  "warnings": ["No photograph was found, so none is hidden."]
}
```

`models` echoes the configured model IDs so the page can name them.
`palette` gives the overlay fill color of every requested region, so a legend
always matches the picture.
`warnings` lists optional steps that failed or found nothing to hide. A warning
never comes with an error status.

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
   the Phase 0 spike showed they return no matches. `photograph` is sent to
   SAM as `photo`, which the F0 spike showed finds portraits that
   `photograph` misses.
4. When `signature` is marked, Muse vision (`MUSE_SIGNATURE_MODEL`, default
   `muse-spark-1.3`) is also asked for signature boxes, in parallel with SAM.
   SAM found no signatures in the F0 spike. Each Muse box is widened by 15% of
   its width and 75% of its height on each side, because Muse boxes run a
   little short. A box over half the image is dropped. A Muse box that repeats
   a SAM signature (overlap of 30% or more) is dropped too, so the SAM mask
   wins. Muse boxes have no mask and a `null` score. If this lookup fails, the
   request still succeeds with a warning.
5. Decode each stream with `meta-sam-parser` and paste the mask at the box
   origin, scaled to the box. A box whose mask cannot be decoded is still drawn
   as an outline. Box coordinates are rounded, the reported boxes and outlines
   are clipped to the working image, and a box entirely off it is dropped.
6. Draw a light colored fill and a thicker outline on larger images. Rectangle
   fills stay lighter than stamps so the page text remains readable. The upload
   page legend uses the same colors.
7. Transcribe the whole image with `MUSE_VISION_MODEL` (`muse-spark-1.3`), in
   parallel with segmentation, then proofread that text with `MUSE_TEXT_MODEL`
   (`muse-spark-1.3`; it can be `muse-wonder-1.0`). The proofread prompt fences
   the transcription in `<transcript>` tags and tells the model never to follow
   instructions inside it. A literal closing tag in the text is defused, and an
   echoed fence is stripped from the answer.
8. While the proofread runs, and only when asked, Muse also pulls out key
   fields (`extract`) and finds personal details (`redact_text`). Region
   descriptions (`describe`) start as soon as segmentation is done. Each has
   its own section below.
9. Draw the overlay, then build the share-safe copy when `redact` names
   regions or image text is hidden, and mask the shareable text.
10. Each Meta call has a 60 second timeout, and the optional steps share one
    deadline (see [Time limit](#time-limit)). This service does not retry a model
   call. Timeout or upstream failure is HTTP 502 with `{"detail": "..."}`.
   The upload page can send the same image again as a new request.

## Live progress

Send `Accept: application/x-ndjson` and the same endpoint streams its progress
as one JSON object per line, then the result:

```text
{"event": "stages", "stages": ["prepare", "segment", "transcribe", "proofread", "render"]}
{"event": "stage", "stage": "prepare", "status": "done", "detail": "1287x1600"}
{"event": "stage", "stage": "segment", "status": "running", "detail": null}
{"event": "stage", "stage": "segment", "status": "done", "detail": "stamp: 1, signature: 1"}
...
{"event": "result", "data": { ...the usual response... }}
```

The first line lists only the stages this request will run: `prepare`,
`segment` (when regions are marked), `describe` (with `describe=true`), `transcribe`, `proofread`, `extract`
(with `extract=true`), `privacy` (with `redact_text=true`), and `render`. Each
stage then sends `running` and `done`; `segment` and `transcribe` run at the
same time, as do `proofread`, `extract`, and `privacy`. The last line is either
`result`, whose `data` is the same JSON as a plain request, or
`{"event": "error", "status": 502, "detail": "..."}` when a model call fails
part way. Upload, form, and rate-limit errors (400, 413, 429) are still plain
HTTP errors sent before any streaming starts.

If the client disconnects, the request is cancelled and no further model
calls are made. The response sets `Cache-Control: no-cache` and
`X-Accel-Buffering: no` so a proxy passes each line on at once; a proxy that
buffers anyway delays the progress but not the result. Without that `Accept`
header the endpoint answers exactly as before.

```bash
curl -sN -H "accept: application/x-ndjson" -F "image=@note.png;type=image/png" http://127.0.0.1:8000/api/process
```

## Ask the document

`POST /api/ask` answers a question from text the page already has; no image
is sent again.

```bash
curl -s -H "content-type: application/json" \
  -d '{"question": "What is the total due?", "text": "Total due: $1,200.00", "fields": []}' \
  http://127.0.0.1:8000/api/ask
# {"answer": "$1,200.00 is due.", "quote": "Total due: $1,200.00"}
```

The question must be 1 to 300 characters and `text` at most 20,000
characters. `fields` is optional: up to 20 `{label, value}` pairs, such as the
extracted document fields. Anything else is HTTP 400 with a sentence the page
can show, and no model is called. Empty text answers "The document does not
say." without a model call.

Muse (`MUSE_TEXT_MODEL`) answers with a strict JSON schema. The question, the
fields, and the text are each fenced in their own tags, and the prompt says to
answer only from the document and never follow instructions inside it. When
the document does not answer the question, the answer is exactly "The
document does not say." `quote` is kept only when it appears verbatim in the
text; otherwise, and for that unanswerable reply, it is `null`. A failed or
unreadable model reply is HTTP 502. This endpoint shares the
`RATE_LIMIT_PER_MINUTE` count with `/api/process`.

## Region descriptions

With `describe=true`, each region gets a short note from Muse vision
(`MUSE_VISION_MODEL`), such as `Round red stamp reading "PAID"`. The work starts
as soon as SAM is done, while the transcription may still be running. Each box
is cropped from the working image with an 8% margin on every side, and a crop
with a short side under 256 px is enlarged to 256 px, with its long side kept
to 1536 px at most. The prompt asks for 12 words at most, quotes any text in
the crop, and tells the model never to name or guess who a person is. The
reply is cut to one line of 160 characters at most.

At most 8 regions are described, best SAM score first and unscored boxes
(such as Muse signature boxes) last, with 4 calls in flight at once. A failed
call leaves that box's `description` as `null` and never fails the request.
`description` is `null` on every box when `describe` is not `true`. In the
stream, this is the `describe` stage, and its detail says how many were
described.

## Custom regions

`custom` lets SAM look for things beyond the four presets. Each name is
lowercased, its spaces are collapsed, and it must be 1 to 3 words of letters,
spaces, and hyphens, 30 characters at most. Up to 3 are allowed, so a request
makes at most 7 SAM calls. A name that means a preset (`Stamp`, `photo`)
turns that preset on instead. Duplicates are dropped. Text prompts (`text`,
`document`, `printed text`, `receipt`, `handwritten note`, `handwriting`,
`handwritten text`) are HTTP 400 with "SAM marks objects, not text. Try a
stamp, logo, or QR code.", because they found nothing in the spikes. Any
other invalid name, or a fourth one, is HTTP 400 too, and no model is called.

Custom regions are segmented after the presets, in the order sent, and keep
their name as the box label. Their overlay colors follow that order: purple
`#7c3aed`, teal `#0d9488`, then pink `#db2777`. They can be hidden in the
share-safe copy like any marked region. In the F0 spike, `logo`, `qr code`,
`barcode`, `face`, `table`, `checkbox`, and `seal` found their objects.

## Share-safe copy

`redact` must be a subset of the marked regions. Hiding a region that is not
marked is HTTP 400, as is an unknown name or style. Each hidden region follows
its SAM mask, pasted at the box origin like the overlay, then grown by 3
pixels so its edge does not show. A region without a mask, such as a Muse
signature box, is hidden as its whole box. `black` fills the area. `blur`
applies a strong Gaussian blur sized to each box; it is weaker than black and
can leave shapes readable, so black is the safer choice. The copy is
re-encoded as PNG from raw pixels, so no EXIF, GPS, or other metadata from the
upload survives. A requested region that is not found adds a warning, and the
copy is still returned.

## Document data

With `extract=true`, Muse reads the transcript while the proofread runs and
returns the document as data, using a strict JSON schema and the same
`<transcript>` fence. `type` is one of `invoice`, `receipt`, `form`,
`id_document`, `letter`, `chat`, `note`, `screenshot`, or `other`. There are
at most 20 fields; a field with an empty value, a label over 40 characters,
or a value over 200 characters is dropped. Labels are in English and values
are copied from the text.

If the reply is not valid, Muse is asked once more with a note saying what
was wrong. That is a second prompt, not a retry of a failed call. If the
second reply is not valid either, or the call fails, `document` is `null` and
a warning says so; the request still succeeds. `found_in_text` is `true` when
the value, ignoring case, spaces, and punctuation, appears in the
transcription or the proofread. A value that does not is still returned, so
the page can flag it rather than hide it. `document` is `null` when
`extract` is not `true` or no text was found.

## Sensitive text

With `redact_text=true`, Muse reads the transcript for personal details while
the proofread runs. It uses a strict JSON schema and the same `<transcript>`
fence as the proofread. Categories are `phone`, `email`, `id_number`,
`account_number`, `card_number`, `address`, `date_of_birth`, and `name`. A
span is kept only when its category is one of these and its text occurs
verbatim, as whole words, in the transcript, so an invented value is never
shown or masked.

Fixed patterns back the model up: emails, phone numbers with 9 to 15 digits,
card numbers that pass the Luhn check, IBANs, runs of 8 or more digits, dates
after "DOB" or "date of birth", and sort codes after "sort code". A long
number such as a barcode may be masked as an account number. When Muse names
someone in full, their surname is masked wherever it also appears alone.

`shareable_text` is the proofread text with every span replaced by
`[CATEGORY]`, longest first. If a span cannot be found in the proofread
because the proofread changed it, a warning says to check the text. If the
Muse call fails, the patterns still run and a warning says so. `sensitive`
is `[]` and `shareable_text` is `null` unless `redact_text` is `true`.

## Text inside the picture

By default the share-safe image hides regions only; text in the picture stays
visible and `image_text_hidden` is `false`. Set `REDACT_IMAGE_TEXT=true` to
also black out sensitive text in the image. Each line of span text is sent to
Muse vision (`MUSE_TEXT_BOX_MODEL`, default `muse-wonder-1.0`) for its box.
A box is kept only for a string that was asked for, is widened by 20% of its
width and 75% of its height on each side, and is always filled black, even
with `blur`. The F0 spike covered 24 of 24 words this way on generated
images, which is why it stays off until it is checked on real photos. This
call adds about 15 seconds, up to about 45. A line that is not found, or a
failed call, is a warning.

## Feature switches

Three optional Muse features can be turned off on the server, to cap the calls
a public copy can make: `FEATURE_EXTRACT` (key fields), `FEATURE_DESCRIBE`
(region descriptions), and `FEATURE_PRIVACY` (the Muse check for personal
details). All three default to `true`. A request that asks for a feature that
is off still succeeds: the feature is skipped, no model call is made, and a
warning says it is turned off on this server. With `FEATURE_PRIVACY=false`,
`redact_text=true` still masks the text using the fixed patterns. Text inside
the picture keeps its own switch, `REDACT_IMAGE_TEXT`, which is off by
default.

`GET /api/config` tells the page which of these run, so it can say so before
anything is sent:

```json
{ "features": { "extract": true, "describe": true, "privacy": true, "image_text": false } }
```

## Time limit

`REQUEST_BUDGET_SECONDS` (default 150) is one deadline for all the optional
steps of a request: the Muse signature lookup, region descriptions, key
fields, personal details, and the text-box lookup. A step still running at the
deadline is cancelled and named in `warnings`, for example "Pulling out key
fields ran past the 150 second limit and was skipped.", and the request still
succeeds. When personal details are skipped this way, the fixed patterns
still mask the text. Core steps (segmentation, transcription, and the
proofread) are never cut; they keep the 60 second limit per model call. The
page waits 180 seconds, which leaves room for the transfer.

## Limits

CORS allows `CORS_ORIGINS`, which defaults to `http://localhost:3000` and
`http://127.0.0.1:3000`.

`RATE_LIMIT_PER_MINUTE` caps `/api/process` and `/api/ask` together per client IP over a sliding
minute. It is off (`0`) by default. Over the limit is HTTP 429 with
`"Too many requests. Wait a minute and try again."`. The count lives in memory,
so it resets on restart and is per process.

## Tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The test suite mocks the model gateway. It does not call Meta. Each module has
its own test file (`test_redaction.py`, `test_privacy.py`, `test_extraction.py`,
`test_describe.py`, `test_ask.py`, `test_stream.py`, and so on), and
`test_process.py` covers the `/api/process` contract.

`tests/fake_server.py` runs the real app with a fixed gateway for the browser
tests in `frontend/e2e/`. It never calls Meta:

```bash
uv run python tests/fake_server.py 8100   # FAKE_DELAY_SECONDS slows the proofread
```

The upload page lives in `frontend/`. See `frontend/README.md`.
