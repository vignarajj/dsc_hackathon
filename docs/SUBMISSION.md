# Submission pack

Ready-to-paste text for the repository's About section and the Cerebral
Valley portal. Deadline: 4 November 2026, 9:00 PM ET; aim for 3 November. I
could not check what the portal's form asks for, so the fields below are a
guess; adjust them to what it shows.

## GitHub About

**Description** (339 of the 350 characters allowed):

```text
Share photos of IDs and forms without the sensitive parts. SAM 3.1 finds signatures, photos, stamps or anything you name; Muse reads and proofreads the page and pulls out its fields. One click gives a share-safe copy: regions hidden, personal details masked, no metadata. FastAPI + Next.js. Meta Global AI Developer Hackathon, Indie track.
```

**Website:** `https://dsc-hackathon.vercel.app`

**Topics** (keep the current ones, add the last four):
`computer-vision`, `document-processing`, `fastapi`, `hackathon`, `meta-ai`,
`muse`, `nextjs`, `ocr`, `proof-reading`, `python`, `sam`, `segmentation`,
`typescript`, `privacy`, `redaction`, `pii`, `structured-extraction`.

## Portal text

**Name:** Document screenshot cleaner

**One line:** Photograph a document, get a copy that is safe to share.

**Description:**

People photograph IDs, forms and bank slips and send them over chat every day,
signatures, faces and account numbers included. Drop the photo in. SAM 3.1
finds the signature, the photo, the stamp, or anything you name. Muse reads the
page, fixes the text, pulls out the document type and key fields, and spots
the phone numbers, emails and ID numbers. One click gives a copy that is safe
to share: the chosen regions are hidden with a black box or a blur, personal
details in the text are replaced by `[PHONE]`, `[NAME]` and so on, and the file
carries no location or camera data. Nothing you upload is stored.

**How it uses Meta models:**

- SAM 3.1 segments stamps, photos, rectangles and up to three things the user
  names; its masks shape the overlay and the hiding.
- Muse Spark transcribes and proofreads the page, boxes signatures (which SAM
  did not find in testing), extracts the key fields, finds personal details,
  describes regions and answers questions about the document.
- Muse Wonder locates sensitive words inside the picture, behind a switch that
  is off on the public copy.

**Built with:** FastAPI, Next.js, Python 3.14, TypeScript, Docker, Render and
Vercel.

**Links:**

- Repository: https://github.com/vignarajj/dsc_hackathon
- Live copy: https://dsc-hackathon.vercel.app (it sleeps when idle, so the
  first request can take a minute; it allows 10 requests a minute in total)
- Demo video: add the link once it is recorded.

**Honest limits** (say these if the form asks):

- Measured on pages made for the app, not on real phone photos or real
  handwritten signatures.
- Text inside the share-safe picture is not hidden by default; the page says
  so and offers the masked text instead.
- One page at a time; no accounts and no saved history.

## Steps that need you

These change the public face of the project, so I have not run them. Each is a
single command with the personal account's token if you want me to run it, or
you can use the GitHub settings page.

1. **Spend alert** on the Meta key. Do this before sharing the URL.
2. **Delete the stale branch**, which holds nothing that `main` lacks:
   `git push origin --delete old-feature-branch`
3. **About section**:
   `gh repo edit vignarajj/dsc_hackathon --description "<text above>" --homepage https://dsc-hackathon.vercel.app --add-topic privacy,redaction,pii,structured-extraction`
4. **Make the repo public**:
   `gh repo edit vignarajj/dsc_hackathon --visibility public --accept-visibility-change-consequences`
5. **Submit on the portal** with the text above and the video link.
6. After judging: suspend the Render service, remove the Vercel project, and
   revoke the Meta key if it was used only for this (`docs/DEPLOY.md` §5).
