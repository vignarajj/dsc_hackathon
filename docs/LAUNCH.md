# Launch tracker

Everything from feature-complete to submission. All features (F0–F8), the
hardening, and the deploy configs are merged; their history is in
`Feature_Expansion_Plan.md` §13. What is left here needs live Meta calls,
host accounts, or a person.

Everything here is on `main` as of 27 Oct 2026 (`c3f5678`). Update this table in every commit that changes an item. `Status` is one of
`Not Started`, `In Progress`, `Done`, or `Blocked` (with the blocker named).
Dates are from the expansion plan's schedule (§7): feature freeze 31 Oct,
submission 3 Nov, 4 Nov as buffer.

| # | Item | Owner | Needs | Target | Status | Notes |
|---|------|-------|-------|--------|--------|-------|
| 1 | Merge the feature work into `main` | You | Green CI | 27 Oct | Done | [vignarajj/dsc_hackathon#1](https://github.com/vignarajj/dsc_hackathon/pull/1), rebase-merged as 17 commits; `main` at `07a4401`. Backend, frontend, e2e, and GitGuardian passed on the PR; e2e passed on GitHub for the first time. On 27 Oct the launch tracker and the live-run results were pushed to `main` as a fast-forward (`c3f5678`), so `main` now matches the working branch. |
| 2 | Live session: real-photo checks and evaluation | You, with photos | 2–3 phone photos of signed pages and 1 with a passport-style photo, no real personal data; a go on more calls | 31 Oct | In Progress | Four-sample run done on 27 Oct with a 40-call cap (all 40 used, none failed): 4 of 4 pages pass; results in the expansion plan §14. Still needed: real photos, real signatures, F1c, and region descriptions. |
| 3 | Deploy a public copy | You | Render and Vercel accounts, the Meta key | 1 Nov | Not Started | Follow `docs/DEPLOY.md`. The first Render build is also the first real build of `backend/Dockerfile`. |
| 4 | Demo video and final README | You | Items 2 and 3 done | 2 Nov | Not Started | Script in the expansion plan §9. |
| 5 | Repo public, About section, submit | You | Items 3 and 4 done | 3 Nov | Not Started | The GitHub description still describes the first version. |
| 6 | Prompts in one `prompts.py` | You | Nothing | Any time | Not Started | Optional tidy-up; not needed for the demo. |

## 2. Live session

Steps:
1. Run `backend/scripts/smoke.py --yes --ask` on the four samples and the
   photos, against a local API with the real key.
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
   `smoke.py --yes --ask --base-url <API URL>`.
5. A spend alert or limit on the Meta key.

Done when: every check passes on the public URLs.

## 4. Demo video and final README

Steps:
1. Record 60–90 seconds following the expansion plan §9, on the public copy.
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
