# Deploying a public copy

The API runs as a Docker container on Render; the page runs on Vercel. Both
are set up from this repository. Anyone who can reach a public copy can spend
the Meta key, so the steps below cap that before the URL is shared, and the
copy should come down after judging.

The page calls the API straight from the browser, so the API host must hold a
request open for up to three minutes and pass a streamed response through as
it is written. Render does both. Any host that runs a Docker image and does
the same works too (Fly.io, Railway); use `backend/Dockerfile` and the same
environment variables.

## 1. The API on Render

1. In Render, choose New, then Blueprint, and pick this repository. Render
   reads `render.yaml` and creates the `dsc-api` web service from
   `backend/Dockerfile`.
2. Fill in the two values the blueprint leaves blank:
   - `META_API_KEY`: the Meta Model API key.
   - `CORS_ORIGINS`: leave it as a placeholder for now, such as
     `https://example.invalid`; step 3 sets the real page URL.
3. Deploy. The service is healthy when `GET /api/health` answers
   `{"status":"ok"}`. Note its URL, for example `https://dsc-api.onrender.com`.

The blueprint sets these for a public copy:

| Name | Value | Why |
|---|---|---|
| `RATE_LIMIT_PER_MINUTE` | `10` | For `/api/process` and `/api/ask` together. Meant per visitor, but on Render it is shared by everyone (see below). |
| `FEATURE_DESCRIBE` | `false` | Region descriptions cost up to 8 calls per image. |
| `FORWARDED_ALLOW_IPS` | `10.0.0.0/8,172.16.0.0/12,192.168.0.0/16` | So the rate limit sees each visitor's address. See below. |
| `plan` | `starter` | A free instance sleeps and takes about a minute to wake. |

Every other setting keeps its default; the root README lists them. Set
`FEATURE_EXTRACT=false` or `FEATURE_PRIVACY=false` to cut further.
`REDACT_IMAGE_TEXT` stays off until it is checked on real photos.

### The rate limit behind a proxy

Render's proxy forwards each request and appends the visitor's address to
`X-Forwarded-For`. uvicorn only trusts that header from the addresses in
`FORWARDED_ALLOW_IPS`, and takes the first address from the right that is not
one of them. With the private ranges above, that is the real visitor.

Never set `FORWARDED_ALLOW_IPS` to `*`. uvicorn then takes the leftmost
address, which the visitor writes themselves, so anyone can send a new
made-up address with each request and skip the limit.

Check it after the deploy, with the bad uploads in step 4: the one after the
limit must be HTTP 429. Then try one from a second network at once; it should
not be 429. If the second network is refused too, Render's proxy is not
connecting from a private address and every visitor shares one limit.

That is what happened on 2 Nov: a phone on another network got 429 while the
limit was tripped from this machine (expansion plan §16). It fails safe (the
key is still capped), so the public copy runs with `RATE_LIMIT_PER_MINUTE=10`
for everyone together, a spend alert on the key, and a take-down after
judging. Keying on the visitor needs the address Render's front passes; that
was not worked out.

## 2. The page on Vercel

1. In Vercel, import this repository and set the root directory to
   `frontend`. `frontend/vercel.json` sets the framework, the pnpm install (pinned with
   `npx pnpm@11.5.2`, since Vercel's own pnpm 9 rejects `pnpm-workspace.yaml`),
   and the build command.
2. Add the environment variable `NEXT_PUBLIC_API_BASE_URL` with the API URL
   from step 1, for example `https://dsc-api.onrender.com`. It is read at build
   time, so redeploy after changing it.
3. Deploy, and note the page URL, for example `https://dsc-cleaner.vercel.app`.

## 3. Connect them

1. In Render, set `CORS_ORIGINS` to the page URL from step 2, with no
   trailing slash. More than one is comma-separated.
2. Redeploy the API.

## 4. Check the public copy

Run these before sharing the URL, and again before recording the demo.

```bash
API=https://dsc-api.onrender.com

curl -s $API/api/health          # {"status":"ok"}
curl -s $API/api/config          # describe should be false

# Progress must arrive line by line, not all at the end. Watch the lines
# appear over several seconds; if they all arrive at once, something buffers.
curl -sN -H "accept: application/x-ndjson" \
  -F "image=@frontend/public/samples/invoice.jpg;type=image/jpeg" $API/api/process | cut -c1-80

# The rate limit, with no model calls: the limit is checked before the upload
# is, so with a limit of 10, eleven bad uploads give 400 ten times and then
# 429. Wait a minute after this before the smoke test, or it counts against
# the same limit.
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "$i: %{http_code}\n" \
    -F "image=not-an-image;filename=x.png;type=image/png" $API/api/process
done
# Expect ten 400s, then 429. Run one from a second network within the minute;
# it should be 400, not 429 (on Render today it is 429; see above).

# The live smoke test: about 9 calls per page, 40 with --ask on the samples.
# --delay 13 keeps it under a limit of 5 a minute, since each page and each
# question counts as one request. With a limit of 10 it is not needed.
cd backend && uv run python scripts/smoke.py --yes --ask --delay 13 --base-url $API
```

Then open the page, clean a sample, and check that the step list fills in,
each tab shows its result, and Cancel returns the page to idle.

## 5. Spend and take-down

- Set a spend alert, or a hard limit if the account allows one, on the Meta
  key before sharing the URL.
- Watch the Render logs. They hold region names, counts, the text's length,
  and error types only, never the text or the image.
- After judging, suspend or delete the Render service and remove the Vercel
  project, then revoke the key if it was used only for this copy.
