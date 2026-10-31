# Shot list

Three clips feed the recording scenes of the demo video. Until they exist, those scenes render a labelled placeholder and the render logs a warning per missing file.

## Setup

- Browser window 1920x1080, app at `http://localhost:8080`, dark theme, bookmarks bar hidden.
- QuickTime screen recording, H.264 `.mov`. Save to `video/public/recordings/<file>`.

## Clips

### `inspect-metal-nut.mov` (scene 3, keyless)

Inspect page, "Try a sample", "Metal nut, bent". Hold 5 s on the FAIL verdict and its missed-defect reason.

### `screw-flip.mov` (scene 4, needs `META_API_KEY` in `.env`, restart compose)

1. Inspect, "Screw, scratched head". Verdict PASS, hold 3 s.
2. Replace the rules box text with exactly:

   `FAIL any scratch or scuff on the screw head, however small; compare the head against the reference. PASS otherwise.`

3. Re-run. Verdict FAIL, hold 5 s on the ruling.

Do not paraphrase the rule: shorter wording stays PASS, only rules that tell the judge to compare against the reference flip it. The first take costs one judge call; retakes with the identical text replay from cache. The overlay box covers the whole screw, so frame on the ruling, not the box.

### `line-mode.mov` (scene 7, camera and a real part)

Line page, allow the camera, show an empty background, place the part and wait for auto-inspect, then swap parts 2-3 times so the tally moves. QuickTime does not capture browser audio by default; enable system audio or the FAIL tone is lost.

## After dropping the files in

`npm run studio`, adjust the `zoom` keyframes in `src/script.ts`, then `npm run render`.
