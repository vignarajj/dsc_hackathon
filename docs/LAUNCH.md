# Launch tracker

Everything from feature-complete to submission. All features (F0–F8), the
hardening, and the deploy configs are merged; their history is in
`Feature_Expansion_Plan.md` §13. What is left here needs live Meta calls,
host accounts, or a person.

On 27 Oct 2026 this tracker and the live-run results were pushed to `main` (`c3f5678`). Update this table in every commit that changes an item. `Status` is one of
`Not Started`, `In Progress`, `Done`, or `Blocked` (with the blocker named).
Dates are from the expansion plan's schedule (§7): feature freeze 31 Oct,
submission 3 Nov, 4 Nov as buffer.

| # | Item | Owner | Needs | Target | Status | Notes |
|---|------|-------|-------|--------|--------|-------|
| 1 | Merge the feature work into `main` | You | Green CI | 27 Oct | Done | [vignarajj/dsc_hackathon#1](https://github.com/vignarajj/dsc_hackathon/pull/1), rebase-merged as 17 commits; `main` at `07a4401`. Backend, frontend, e2e, and GitGuardian passed on the PR; e2e passed on GitHub for the first time. On 27 Oct the launch tracker and the live-run results were pushed to `main` as a fast-forward (`c3f5678`), so `main` now matches the working branch. |
| 2 | Live session: real-photo checks and evaluation | You, with photos | 2–3 phone photos of signed pages and 1 with a passport-style photo, no real personal data; a go on more calls | 31 Oct | In Progress | Four-sample run done on 27 Oct with a 40-call cap (all 40 used, none failed): 4 of 4 pages pass; results in the expansion plan §14. Second run on 2 Nov, no photos available, 28 of 35 calls: a generated receipt, F1c, region descriptions and the QR code all pass (§15). Real photos and real signatures stay unmeasured and are left out of the submission claims. |
| 3 | Deploy a public copy | You | Render and Vercel accounts, the Meta key | 1 Nov | In Progress | Live on 2 Nov: API on Render (Free, by hand), page at `https://dsc-hackathon.vercel.app`. Health, CORS, streaming and the smoke test (4 of 4) pass; see the expansion plan §16. A Pixel 3 click-through with Cancel also passes (§16). The second-network check failed: a phone on another network got 429 while this Mac's limit was tripped, so all visitors share one limit (§16). Limit raised to 10, shared by all visitors, and checked (11th bad upload is 429). A rerun of the smoke test with the receipt passed 5 of 5. Open: the spend alert. |
| 4 | Demo video and final README | You | Items 2 and 3 done | 2 Nov | In Progress | Shot list in `docs/DEMO.md`. The README has the live link, the results, the hosting section, screenshots in light and dark, and GIFs of the desktop and the Pixel (UI review in the expansion plan §17); `demo/ui-session.webm` is a reference recording. The narrated demo video, `demo/final-demo.mp4` (62 s, captions plus computer voice, QR take included), was recorded on 3 Nov; it waits for your watch-through. |
| 5 | Repo public, About section, submit | You | Items 3 and 4 done | 3 Nov | Not Started | The About text, topics and portal text are drafted in `docs/SUBMISSION.md`, with the commands. The audit found no keys in history and no secret files; the stale branch `old-feature-branch` was fully merged and was deleted on 2 Nov (only `origin/main` is left). The About description, website and topics were updated on 3 Nov; the repository is already public. |
| 6 | Prompts in one `prompts.py` | You | Nothing | Any time | Done | A pure move: the 13 requests the gateway sends are byte for byte the same as before. See `backend/README.md` (Code layout). |

## 2. Live session

Steps:
1. Run `backend/scripts/smoke.py --yes --ask` on the four samples and the
   photos, against a local API with the real key. Name a receipt photo
   `receipt.jpg` to get the receipt checks, add `--describe` for the region
   descriptions (up to 8 more calls per page), and start the API with
   `REDACT_IMAGE_TEXT=true` for the F1c trial (1 more call per page).
2. Acceptance checks from the expansion plan:
   - F1: on the signed form, the signature and photo are fully hidden with no
     visible edge, phone and ID numbers are masked in the shareable text, and
     the downloaded file has no EXIF.
   - F2: "logo" finds the logo on the letterhead in its own color.
   - F3: the invoice, receipt, and form each get the right type and 3 or more
     grounded fields.
3. Decide, from the results:
   - whether Muse signature boxes hold up on real signatures;
   - whether `REDACT_IMAGE_TEXT` (F1c) can be turned on;
   - whether region descriptions should be on by default on the page;
   - whether the overlay stays PNG (expansion plan §5.4), from its size on
     real photos.
4. Fill in the evaluation sheet (expansion plan §6) and put the numbers in
   the README.

Done so far (27 Oct, four generated samples, 40 calls): steps 1 and 2 ran on
those pages, and step 4 has numbers for them; see the expansion plan §14. F1,
F3, and F7 pass, and F2 passes in part (the logo mark was found, but a stamp
was also boxed as a logo). The overlay stays PNG. Left for real photos: the
signature check on real handwriting, whether F1c can be turned on, whether
region descriptions should be on by default, and a receipt.

Second run (2 Nov, 28 calls, still generated pages): the receipt, F1c and
region descriptions pass, and "QR code" is found; see the expansion plan §15.
F1c stays off by default, since it adds 16 to 29 s and clips field labels, and
descriptions stay off by default on the page. Real handwritten signatures and
real phone photos remain unmeasured.

Done when: the checks above pass or each failure is written down with what
was changed or cut, and the decisions are recorded in the expansion plan.

## 3. Deploy a public copy

Steps (detail in `docs/DEPLOY.md`):
1. Render: create the `dsc-api` service from `render.yaml`; set
   `META_API_KEY`.
2. Vercel: import `frontend/`; set `NEXT_PUBLIC_API_BASE_URL` to the API URL.
3. Set `CORS_ORIGINS` on the API to the page URL and redeploy.
4. Checks: health and config, progress arrives line by line, the rate limit
   (the sixth request in a minute is 429, a second network still works), and
   `smoke.py --yes --ask --delay 13 --base-url <API URL>`. The rate-limit check
   uses six bad uploads, so it spends no model calls.
5. A spend alert or limit on the Meta key.

Done when: every check passes on the public URLs.

## 4. Demo video and final README

Steps:
1. Record 60–90 seconds on the public copy, following `docs/DEMO.md` (the expansion plan §9, cut to what the public copy shows).
2. Save it in `demo/` and link it from the README.
3. README: the evaluation numbers, a screenshot or GIF of the share-safe
   slider, and the public URL.

Done when: the video is in the repo and the README matches the public copy.

## 5. Submit

Steps:
1. Make the repository public.
2. Update the About section: description, website (the public page), and
   topics.
3. Submit on the Cerebral Valley portal before 4 Nov, 9:00 PM ET; aim for
   3 Nov.
4. After judging: take the public copy down and revoke the key if it was
   used only there (`docs/DEPLOY.md` §5).

Done when: the portal shows the submission.

## Decisions

Questions asked one at a time, each with a recommended answer; the answer is
recorded here and the docs are updated to match.

| # | Date | Question | Answer | Effect |
|---|------|----------|--------|--------|
| 1 | 2 Nov | Narrate the demo video? | Computer voice plus on-screen captions (recommended) | The video is made with Playwright, burned-in captions and a macOS `say` voice-over; the script is in `docs/DEMO.md`. It reads fine on mute, and your own voice can replace the track later. |
| 2 | 2 Nov | Include the QR-code take? | Yes (recommended) | The video has a second clean on "Invoice with a PAID stamp" with "+ QR code" on (9 more calls, wait cut), spliced into the 25 to 40 s slot; `docs/DEMO.md` no longer calls it optional. |
| 3 | 2 Nov | Where is the video hosted? | A file in the repo only, no YouTube (your answer; I had recommended unlisted YouTube) | The video is an H.264 `.mp4` in `demo/` (kept under 25 MB, well below GitHub's 100 MB limit), linked from the README and from the portal text as a `github.com/.../blob/main/demo/...` URL. The repo must be public before that link works for judges. If the portal only takes a file upload, upload the same `.mp4`. |
| 4 | 3 Nov | When do About and public happen? | About text now, repo public only after the video is committed and checked (recommended) | About description, website and topics were set on 3 Nov. The repo turned out to be public already (checked with the personal token and anonymously, HTTP 200), so there is no step to make it public; the video link works as soon as the file is pushed. |
