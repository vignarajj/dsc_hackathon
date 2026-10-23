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
- Optional multipart field `custom`: up to 3 more things for SAM to find, comma-separated,
  such as `logo,qr code`.
- Optional multipart field `redact`, a comma-separated list of marked regions to hide
  in a share-safe copy. Omit it for no copy.
- Optional multipart field `redact_style`: `black` (default) or `blur`.
- Optional multipart field `redact_text`: `true` to find personal details in the text and
  return a masked copy. Default `false`.

```bash
curl -s -F "image=@note.png;type=image/png" http://127.0.0.1:8000/api/process
curl -s -F "image=@note.png;type=image/png" -F "concepts=rectangle" http://127.0.0.1:8000/api/process
curl -s -F "image=@form.jpg;type=image/jpeg" -F "redact=signature,photograph" http://127.0.0.1:8000/api/process
```

## Response

```json
{
  "boxes": [{ "x": 0, "y": 0, "w": 100, "h": 50, "label": "stamp", "score": 0.97 }],
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
7. Transcribe the whole image with `muse-spark-1.3`, then proofread that text
   with the same model. `MUSE_TEXT_MODEL` can be set to `muse-wonder-1.0`.
   The proofread prompt fences the transcription in `<transcript>` tags and
   tells the model never to follow instructions inside it. A literal closing
   tag in the text is defused, and an echoed fence is stripped from the answer.
8. When `redact` names regions, build the share-safe copy. It is described
   below.
9. Each Meta call has a 60 second timeout. This service does not retry a model
   call. Timeout or upstream failure is HTTP 502 with `{"detail": "..."}`.
   The upload page can send the same image again as a new request.

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
