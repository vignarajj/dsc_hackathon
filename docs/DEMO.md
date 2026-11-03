# Recording the demo

A 60 to 90 second screen recording of the public copy, following the plan in
`Feature_Expansion_Plan.md` §9 but cut to what the public copy can show. The
copy has region descriptions and text hiding in the picture turned off, so the
"region notes" shot is left out.

## Before you press record

1. **Wake the API.** The Free instance sleeps when idle. Open
   https://dsc-api-xxzv.onrender.com/api/health and wait for `{"status":"ok"}`.
   Do it again about a minute before recording.
2. **Make sure nobody else is using the page.** The limit is 10 requests a
   minute across all visitors. A clean is one request and a question is another.
3. **Warm up with one clean** of the signed form, then reload the page. It
   takes 20 to 35 seconds, and a first run after a sleep can take longer.
4. **Set up the screen.** A clean browser window with no bookmarks bar, 1080p,
   dark or light but not mixed. macOS: Shift-Command-5, record the window.
   Close notifications.
5. **Have the check ready.** Reload the page so no old result is showing, and
   keep the console closed.

## Shot list

| Time | Show | Say |
|---|---|---|
| 0 to 10 s | The page at the top, switch Dark then Light with the toggle at the top right, then the four samples. | "People photograph IDs, forms and bank slips and send them over chat every day, signature, face and account number included." |
| 10 to 25 s | Click "Signed form with a photo", press Clean screenshot. The step list ticks. Cut or speed up the wait. | "SAM 3.1 finds the regions while Muse reads the page." |
| 25 to 40 s | Overview tab. Drag the slider. Point at the stamp, signature and photo. | "SAM marks the stamp, the signature and the photo." |
| 40 to 55 s | Data tab: the type, the summary, the fields. Click Download JSON. | "Muse turns the photo into data, and checks every field against the text." |
| 55 to 75 s | Share-safe tab. Drag the slider. Scroll to the shareable text with `[PHONE]` and `[EMAIL]`. | "One click hides the signature and the photo, strips location and camera data, and masks the personal details in the text." |
| 75 to 90 s | Back to the top of the page. | "Built for the paperwork in everyone's world." |

Second take (decided 2 Nov, see `docs/LAUNCH.md` Decisions), to show "SAM finds
anything you can name": choose "Invoice with a PAID stamp", click "+ QR code", press Clean screenshot,
and show the purple box on the QR code in the Overview. It costs another 9
calls and 20 to 35 seconds, so cut the wait and splice it into the 25 to 40
second slot.

A reference recording of the current page, made with Playwright on the public
copy, is `demo/ui-session.webm` (38 seconds; the waiting is sped up and the
pink dot is a cursor added for the recording). The screenshots in the README
were taken the same day, without the cursor.

## What to avoid

- Turning on "Describe each region": it is off on this server and says so.
- Text hiding in the picture: also off on the public copy.
- Anything that suggests real photos were measured. The numbers are from the
  generated sample pages; the README says so.

## If something goes wrong

- **"Too many requests"**: wait a minute, then press Try again.
- **A long wait on the first clean**: the instance was asleep. Reload and retry.
- **No result after 3 minutes**: the page gives up and offers Try again.

## The recorded video

`demo/final-demo.mp4` (3 Nov): 62 seconds on the public copy, 1280x720, captions drawn on the page, a macOS `say` voice (Flo) laid over it, and the two waits sped up 10 times. It follows the shot list above, drops the Download JSON click's file from view, skips the 75 to 90 s "back to top" in favour of a short closing line, and adds the QR take after the Share-safe tab. It used about 18 Meta calls. To make a new one, record again against the public copy and keep it under 25 MB.

## After recording

The video is a file in the repo (decision 3 in `docs/LAUNCH.md`, no YouTube):
`demo/final-demo.mp4`, H.264, under 25 MB. If you record your own, save it
under `demo/` and tell me, and I will link it from the README and convert it
with `ffmpeg -i in.mov -c:v libx264 -crf 28 -vf scale=1920:-2 -an out.mp4`
(drop `-an` to keep the sound). A phone clip of the same flow, recorded on a Pixel 3, is in
the README as `docs/phone-demo.gif`.

To cut a GIF of your own from a recording (change the times and the width):

```bash
ffmpeg -y -i demo.mov -vf "fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" docs/demo.gif
```
