# ZeroShot QC — frontend UI/UX redesign (spec)

Tier L. Every screen a user sees changes, across 6+ substantial source files. There is no auth, API or server change.
Visual reference: `.plans/ui-redesign/prototype.html` (a throwaway mockup). The working copy with images is `.lavish/ui-redesign/proto/index.html`. `.lavish/` is untracked and holds MVTec images (CC BY-NC-SA): **never commit it**. Where prototype and spec disagree, the spec wins.

## Problem

- All 4 pages FAIL the taste-skill inspector today. `frontend/src/index.css` turns `body` dark under `prefers-color-scheme: dark`, but every page hardcodes light Tailwind greys (`bg-white`, `text-neutral-900`, `border-neutral-300`). Dark-OS users get near-invisible titles and white input boxes.
- There is no design system: about 60 duplicated class strings across 4 pages, raw palette colours, no tokens, and the system font.
- Each page has two `h1`s (`App.tsx:17` plus the page's own). Eval numbers are left-aligned without tabular figures. Inspect and Synthetic open on a mostly empty screen.
- Inspect, the main job, reads as a form. The verdict sits below the fold, the reference image is never shown, and detections link to the overlay only on hover.

## Solution

Build a small token-driven design system: Swiss minimal style, Fira Sans + Fira Code, and colour only on data. Rebuild the shell and the 4 pages on it, following taste-skill's `references/app-screens.md` rules:
- flat surfaces;
- a receding nav;
- type-led KPIs;
- honest empty and zero states;
- the product's own name and mark.

Add purposeful motion with `motion`. Then run taste-skill's inspector in a look-and-fix loop until the gate passes.

## Dialectical Outcomes (Why)

| # | Decision | Rejected | Why |
|---|---|---|---|
| 1 | Light "inspection bench" + full dark parity from one token set; a System/Light/Dark switch in the top bar | Light only; dark-first | The body already flips to dark, so tokens fix the root cause. The switch also lets the inspector (which has no colour-scheme flag) test both themes. |
| 2 | Visual + layout/flow rework, **no backend change** | Visual-only reskin; new capabilities (webcam, launch eval) | The biggest gain at zero API risk. New capabilities contradict the RECORD. |
| 3 | Compact top bar: mark, 4 tabs, health dot, theme switch | Left sidebar | Only 4 pages, and Inspect needs width. |
| 4 | `@fontsource/fira-sans` + `@fontsource/fira-code`, bundled | Google Fonts `<link>` | QC stations can be offline. The inspector fails a fallback font. |
| 5 | House primitives in `src/components/` + Tailwind v4 `@theme` tokens | shadcn/Radix | 4 pages don't need a kit, and stock shadcn reads as AI default. |
| 6 | Gate: 0 FAIL on 4 routes × 1440/768/390 × light/dark; each WARN fixed or a named `--allow` with a reason | 0 WARN | Strict, but leaves room for WARNs that don't fit an inspection tool. |
| P1 | Inspect = prototype **C**: Reference card + Under test card side by side (12px gap), full verdict card on the right | A (one image + verdict), B (verdict strip + trio) | The user picked B's two previews and A's verdict card. |
| P2 | One line-icon set (inline SVG sprite, 24px viewBox, stroke 1.8, round caps), no icon library | lucide-react etc. | Tiny, consistent, no dependency. No icons on KPI numbers (a taste rule). |
| P3 | Dark danger red `#ff5c50`; chips on red/amber use dark text in dark mode | the softer `#f2938a` | The user asked for a stronger red. It measures ~5.8:1 on `#18191c`. |
| P4 | Buttons centre icon + label; secondary inline buttons size to their label | — | User feedback. |
| P5 | `motion` (formerly Framer Motion) wherever an animation or transition helps | CSS-only | User request. `motion@14.7.1` peers allow React 18/19. |
| — | Synthetic stays **gallery-only** (no Generate form) | Wire `POST /api/synth/generate` | The approved plan said "keep existing generate controls", but there are none today. The prototype invented them. Adding them would be a new paid capability. |

## Relevant Files (Where)

Modify:
- `frontend/package.json`: add deps `motion`, `@fontsource/fira-sans`, `@fontsource/fira-code`.
- `frontend/index.html`: `<html lang="en">` gets an inline pre-paint theme script (below) and `<meta name="color-scheme" content="light dark">`. Replace the favicon with the reticle mark.
- `frontend/src/index.css`: tokens, `@theme` mapping, base styles, fonts, reduced motion.
- `frontend/src/main.tsx`: import the fontsource CSS and wrap `<App/>` in `<MotionConfig reducedMotion="user">`.
- `frontend/src/App.tsx`: new shell.
- `frontend/src/api.ts`: add `getHealth()`.
- `frontend/src/pages/Inspect.tsx`, `Profiles.tsx`, `Eval.tsx`, `Synthetic.tsx`: rebuilt on primitives.
- `frontend/public/favicon.svg`: the reticle mark.

Create:
- `frontend/src/components/` with `Button.tsx`, `Field.tsx`, `Panel.tsx`, `Alert.tsx`, `VerdictBadge.tsx`, `PageHeader.tsx`, `EmptyState.tsx`, `Icon.tsx` (sprite + `<Icon name>`), `ThemeSwitch.tsx`, `HealthDot.tsx`.
- `frontend/src/theme.ts`: `resolveTheme(stored: unknown): 'system'|'light'|'dark'` and `applyTheme()`.
- `frontend/src/geometry.ts`: `boxPercent(bbox, naturalW, naturalH)`, moved out of `HoverBox` in `Inspect.tsx`.
- Tests: `frontend/src/theme.test.ts`, `frontend/src/geometry.test.ts`, `frontend/src/health.test.ts`.
- `docs/design-system.md`: tokens table and the do/don't rules (short).
- `.plans/ui-redesign/taste/`: final inspector reports and the allow-list with reasons.

## Key Code Context (What)

API shapes the pages render (`frontend/src/api.ts`, unchanged except `getHealth`):
```ts
export interface Detection { id: string; label: string; score: number;
  bbox: [number, number, number, number]; maskRle: MaskRle; areaPx: number;
  lengthPx: number; areaMm2: number | null; lengthMm: number | null; }
export interface DefectRuling { detectionId: string; isRealDefect: boolean;
  ruleViolated: string | null; reason: string; }
export interface Verdict { verdict: "PASS" | "FAIL"; confidence: number;
  rulings: DefectRuling[]; missedDefects: string[]; summary: string; }
export interface ProductProfile { id: string; name: string; defectPrompts: string[];
  rules: string; mmPerPx: number | null; minScore: number; referenceImage: string | null; }
export interface InspectionResult { id: string; profileId: string; detections: Detection[];
  verdict: Verdict; overlayUrl: string; timingsMs: { segment: number; judge: number; total: number }; }
export interface CategoryMetrics { precision: number; recall: number; f1: number; accuracy: number;
  auroc: number; n: number; tp: number; tn: number; fp: number; fn: number; iou: number | null; }
export interface EvalRunSummary { runId: string; mode: string; source: string; adapter: string | null;
  seed: number | null; categories: string[]; nGood: number | null; nDefective: number | null;
  rules: string | null; metrics: { perCategory: Record<string, CategoryMetrics>; overall: CategoryMetrics } | null; }
export interface EvalRunDetail { summary: EvalRunSummary; results: EvalResultRow[]; }
export interface SynthGalleryItem { category: string; defect: string; imageUrl: string; maskUrl: string | null; }
export function resolveFileUrl(url: string): string            // use for every <img src>
async function getJson(path: string, signal?: AbortSignal): Promise<unknown>  // internal helper
```
Exports used by pages: `inspectImage`, `listProfiles`, `getProfile`, `putProfile`, `draftProfileFromSop`, `listEvalRuns`, `getEvalRun`, `listSyntheticGallery`, `ApiError` (+ subclasses).

The backend `GET /api/health` (`backend/app/main.py:59`) returns `{"status":"ok","models":{...}}`.

Inspect behaviour that **must survive** (`Inspect.tsx`):
```ts
// Debounced judge-only re-run: re-posts the same in-memory image bytes
// with edited rules (~500ms). Empty rules are omitted so the backend
// restores profile rules. A new keystroke aborts the stale in-flight
// request so it can never overwrite the newer verdict.
useEffect(() => { ... window.setTimeout(() => runInspect(image, id, trimmed === '' ? undefined : rulesText), 500) ... }, [rulesText])
```
It also keeps: `abortRef` aborting on new runs and unmount, `URL.revokeObjectURL` on preview change, `naturalSize` reset per result, profiles load with AbortController, and `ApiError.detail` shown on error.

The box geometry to extract (`Inspect.tsx` `HoverBox`):
```ts
if (naturalWidth <= 0 || naturalHeight <= 0) return null
const [x, y, w, h] = detection.bbox
left = x / naturalWidth * 100; top = y / naturalHeight * 100; width = w / naturalWidth * 100; height = h / naturalHeight * 100
```

Eval keeps its failure-examples viewer: `isFailure(row)` is `(good && FAIL) || (defective && PASS)`, with a selectable list, an image with an `onError` empty frame, and a `row.imageUrl === null` empty frame. Synthetic keeps grouping by category then defect (`Synthetic.tsx:81`), and the per-item "Image file missing" / "No mask for this pair" / "Mask file missing" frames. Profiles keeps every flow in `Profiles.tsx`: edit + save (`putProfile`), refresh, SOP draft (`draftProfileFromSop`), save-as-new with the overwrite guard (`existingProfile`/`overwriteArmed`), notices and errors.

`vite.config.ts` proxies `/api` and `/files` to `localhost:8000`. `vite preview` inherits `server.proxy`.

## Implementation Algorithm (How)

### Phase 1: Design system
1. Run ui-ux-pro-max: `python3 ~/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/2.15.0/.claude/skills/ui-ux-pro-max/scripts/search.py "industrial quality inspection tool" --design-system -p "ZeroShot QC"`, `--stack react` (or `html-tailwind`), and `--domain ux` checks for focus, forms and data tables. Keep: Swiss minimal style and Fira. Drop: its landing "Hero + CTA" pattern.
2. Read taste-skill `references/app-screens.md` in full before building screens.
3. `index.css`: copy the prototype's three token layers.
   - **Primitives**: the stone/night/navy/green/red/amber/blue scales, `--r-sm:4px`, `--r-md:6px`, `--dur:160ms`.
   - **Semantic** (`--ground --surface --sunken --ink --ink-2 --ink-3 --line --line-strong --accent --on-accent --pass --fail --on-fail --detect --data --pass-tint --fail-tint --focus`), defined for light under `:root, :root[data-theme="light"]`.
   - **Dark** values defined twice: under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {...} }` and under `:root[data-theme="dark"]`.
   - Use the exact dark values from the prototype, with `--fail:#ff5c50`.
4. Map the tokens through Tailwind v4 `@theme inline { --color-ground: var(--ground); ... --font-sans: "Fira Sans", ...; --font-mono: "Fira Code", ... }`, so pages use `bg-surface text-ink border-line text-fail` etc. Add a `.num { font-variant-numeric: tabular-nums }` utility. Body uses `bg-ground text-ink font-sans`, at 15px/1.5.
5. Fonts: `main.tsx` imports `@fontsource/fira-sans/400.css`, `500.css`, `600.css` and `@fontsource/fira-code/400.css`, `500.css`.
6. `docs/design-system.md`: a token table, the type scale (page title 20px/600; section 13px/600 ink-2; body 14–15; KPI 26px/500), spacing (4px grid), and rules:
   - colour on data only;
   - no shadows on cards;
   - no zebra stripes;
   - numbers right-aligned and tabular;
   - no icons on KPIs;
   - one `h1` per page.

### Phase 2: Primitives
- `Button` variants: primary (accent fill), secondary (surface + line-strong border), ghost. Each has `min-h-9` (36px) desktop and 44px touch target via padding at `pointer:coarse`. Content is `inline-flex items-center justify-center gap-1.5`, with optional `icon`. Disabled is opacity 45% with `cursor-not-allowed`.
- `Field`: label + hint + control slot + error (`aria-describedby`). Controls get the `.ctl` styles from the prototype.
- `Panel` (+ `PanelHeader`), `Alert` (`role="alert"` error / `role="status"` notice, tinted by token), `VerdictBadge` (PASS/FAIL word + icon, colour by token), `PageHeader` (the only `h1`, plus subtitle and actions slot), `EmptyState` (dashed frame, icon, title, body, optional action).
- `Icon`: one hidden `<svg>` sprite mounted once in `App`. `<Icon name="scan" />` renders `<svg class="ic" aria-hidden><use href="#i-scan"/></svg>`. Names and paths are copied from the prototype sprite: scan, sliders, chart, sparkles, check, x, alert, clock, pencil, upload, save, file, refresh, sun, moon, monitor, layers, list, eye.
- `focus-visible` ring: `outline:2px solid var(--focus); outline-offset:2px` globally.

### Phase 3: Shell
- `theme.ts`: `resolveTheme(v)` returns `'light'|'dark'` when given exactly those strings, else `'system'`. `applyTheme(t)` sets `document.documentElement.dataset.theme` for light/dark, removes it for system, and writes `localStorage['zsqc-theme']` inside try/catch.
- `index.html` pre-paint script (inline, before CSS) reads the same key inside try/catch and sets `data-theme`, to avoid a flash.
- `api.ts` `getHealth(signal)`: `getJson('/api/health')`. Returns `'ok'` when `data.status === 'ok'`, else `'down'`. **Never throws**; it catches every error except AbortError.
- `HealthDot` polls on mount and every 30s (cleared on unmount). Dot is `--pass`/`--fail`/`--ink-3` (checking). Label: "Backend online" / "Backend unreachable", hidden ≤1000px but kept as `aria-label`.
- `App.tsx` top bar: sticky, 52px, `bg-surface border-b border-line`.
  - Left: reticle mark (SVG, `--accent`) + "ZeroShot QC" (no `h1`). Name hidden ≤640px.
  - Tabs: `NavLink` with icon + label. Active is ink colour + a 2px ink underline animated with `motion` `layoutId="tab-underline"`.
  - Right: HealthDot + ThemeSwitch (segmented System/Light/Dark with icons; labels hidden ≤1000px).
  - ≤640px: the bar wraps, and tabs go to a second row.
- `main`: `max-w-[1360px] mx-auto px-5 pt-5 pb-16`.

### Phase 4: Inspect (prototype C)
- `PageHeader`: "Inspect" + "Segment candidates, then judge them against the profile rules." The actions slot holds a run bar grid: Profile `select`, Image drop zone, and Inspect button (primary, scan icon, label "Inspect" / "Inspect again" after a result / "Inspecting…").
- Drop zone: a `label` wrapping a visually-hidden `input type=file accept="image/*"`. `onDragOver` preventDefault + highlight; `onDrop` takes `dataTransfer.files[0]` if `type.startsWith('image/')`, else shows the Alert "Drop an image file (PNG or JPG).". It feeds the same handler as `handleFileChange`. It shows the thumbnail + filename + natural size once loaded.
- No file yet: a two-column `EmptyState`. Left is a big dashed drop target ("Drop a part photo here", "Choose file" button with upload icon). Right is a panel with the selected profile's rules, "Looks for" prompt chips, and a disabled Inspect button.
- File chosen: grid `minmax(0,2fr) minmax(340px,0.95fr)`, stacking ≤1000px.
  - Left: `.previews` grid of 2 equal columns with a 12px gap (1 column ≤640px). It holds:
    - **Reference card**: header with check icon, "Reference", and the file name. The image is `resolveFileUrl(profile.referenceImage)`. Null or `onError` gives an EmptyState frame "No reference set for this profile".
    - **Under test card**: header with scan icon, "Under test", and "N candidates". The image is `result?.overlayUrl ?? previewUrl`. Boxes come from `boxPercent`.
  - Below both cards sits a legend row spanning them: "Ruled a defect" (fail outline), "Cleared by judge" (detect outline), and the hint "Hover a box or a ruling to link them".
  - Right: the verdict card.
    - Before any result, it shows "Press Inspect to get a verdict with per-detection reasons."
    - After a result:
      - `VerdictBadge` (34px, icon) + "confidence 90.0%" + summary.
      - "Rulings · N candidates" with "M missed defects".
      - An ordered list: numbered chip (fail bg if `isRealDefect`, else detect bg), label, a Defect pill (alert icon, fail tint) or Cleared pill (check icon), "score 0.85 · 198.9 mm²" (px when `areaMm2` is null), the reason, and "Rule cited: …" when `ruleViolated`.
      - A missed defects line if any.
      - A timings `dl` (3 cells, clock icons, tabular).
      - The rules override textarea (pencil icon label, hint "Applies to this run only. Clear it to go back to the profile rules."), with a status line while re-judging ("Re-judging with edited rules · segmentation reused").
- Box ↔ ruling link: `hoveredId` state, set on pointerenter/focus of a box or ruling `li` and cleared on leave/blur. A highlighted box gets `box-shadow: 0 0 0 3px color-mix(ink 35%)`, and a highlighted row gets `bg-sunken`. Boxes and rows are focusable (`tabIndex=0`) with an aria-label "1: chip on bottle, defect".
- Box colour: a box whose ruling has `isRealDefect` uses `--fail` and its tag `--on-fail`. Otherwise it uses `--detect` with dark text `#18181a`. Number = index + 1 in `detections` order. A ruling is matched to its box by `detectionId`.
- No detections: a status under the image, "No defects detected. The image is shown unmarked."

### Phase 5: Profiles
- `PageHeader` "Profiles" / "What each product is checked for, and the rules the judge applies." Its actions hold "Draft from SOP" (file icon). The button scrolls to and focuses the SOP panel.
- Grid `260px minmax(0,1fr)` (stacks ≤1000px).
  - Left panel: "N profiles" + Reload (refresh icon). The list button shows the name with a mono id under it and "k prompts" on the right. Selected has `bg-sunken` + `aria-current`.
  - Right panel: header with the name + mono id + "Ids are fixed once created". The form has these fields: Name; Defect prompts (mono textarea, hint "What the segmenter looks for, one per line"); Rules (hint "Plain English. The judge cites these when it fails a part."); then a 3-column row: mm per px (hint "Blank = report pixels only"), Min score (hint "Candidates below this are dropped"), Reference image (path input + 56px thumbnail).
  - A save bar at the bottom: Save profile (save icon) + an "Unsaved changes" hint when the draft differs from the loaded profile.
- SOP panel below: SOP text + category name → Draft. The draft preview is a `dl`, plus Save-as id, overwrite warning Alert, and Save as new. All logic stays the same.
- Loading: EmptyState skeleton text "Loading profiles…". Empty: the existing copy.

### Phase 6: Eval
- `PageHeader` "Eval" / "Runs scored on MVTec AD. Launch new runs from the CLI."
- Grid `260px minmax(0,1fr)`. Left is the runs list. Each row shows a friendly mode name, the mono run id (ellipsis), and overall F1 on the right (tabular, `--ink-3` when 0.000).
- Mode names: `sam_only` "SAM only", `sam_judge` "SAM + judge", `sam_judge_ref` "SAM + judge + reference". An unknown mode prints raw.
- Right, the run panel:
  - Header: mode name + mono id, and on the right "source · seed s · k categories · n images".
  - KPI `dl`: F1 (in `--data`), Precision, Recall, AUROC, Accuracy, as 26px tabular numbers, 5 columns (3 ≤1000px).
  - Confusion line: "True fail tp · True pass tn · False fail fp · Missed fn".
  - Per-category table:
    - Category, an F1 bar (6px, `--data`), then F1, Precision, Recall and AUROC.
    - Number columns are right-aligned and tabular.
    - Use 1px row rules only: no zebra stripes and no header band.
  - `null` metrics: a framed "No metrics recorded for this run".
- Ablation panel, shown only when ≥2 runs share the selected run's `source`, `seed` and sorted `categories`. It has one row per mode: name, a 10px bar, and overall F1. The selected run uses `--data`, the others `--line-strong`. The title is "Ablation · same seed, same N images".
- Failure examples panel: the existing list + viewer, restyled. The empty state is "No failures in this run — every verdict matches its label."
- Zeros print as `0.000`; a missing value prints `—` in `--ink-3`.

### Phase 7: Synthetic (gallery only)
- `PageHeader` "Synthetic" / "Generated defect images with exact masks, for eval when real defects are scarce." Actions: a "Show masks" checkbox (eye icon).
- Filter chips: "All · N", then one chip per `category / defect · n` (`aria-pressed`).
- Grid `repeat(auto-fill,minmax(220px,1fr))` gap 16. Each card shows a square image (`object-cover`), the mask overlaid (`mix-blend-mode:screen`, `image-rendering:pixelated`, opacity 0 → 0.85 when Show masks is on), and a footer with "category / defect" + mono index. The existing missing-file frames are kept.
- Grouping is now the filter, not stacked headings. Keep the existing `groups` helper for chip counts.
- **No Generate form.**

### Phase 8: Motion pass
All motion uses `motion/react`, at 150–250ms ease-out.
- **Verdict card on a new `result.id`:** `initial {opacity:0,y:6}`, then animate in. Rulings stagger by 40ms.
- **Boxes:** draw in after the overlay `onLoad` (opacity + scale 0.96 → 1).
- **Re-judge:** the verdict content crossfades (`AnimatePresence mode="wait"` keyed by result id).
- **Pages:** route content fades (opacity only, 150ms) keyed by `location.pathname`.
- **Tabs:** the underline slides via `layoutId`.
- **Synthetic grid:** `layout` on cards when the filter changes.
- **Enter/exit:** `AnimatePresence` on Alerts, the SOP draft preview, and the overwrite warning.
- **Mask overlay:** a CSS opacity transition is fine.

Forbidden:
- animating changing numbers;
- looping or decorative motion;
- animating width or height (use transform and opacity).

`MotionConfig reducedMotion="user"` plus the existing CSS reduced-motion rule in `index.css` means nothing moves when the OS asks for reduced motion.

### Phase 9: Taste gate loop
1. `cd backend && USE_FAKE_ADAPTERS=true .venv/bin/uvicorn app.main:app --port 8000`. Fake adapters only: no keys, no real model calls.
2. `cd frontend && npm run build && npx vite preview --port 4173 --strictPort`.
3. For each route `/`, `/profiles`, `/eval`, `/synthetic`, run `node ~/.claude/skills/design-taste-frontend/scripts/inspect.mjs http://localhost:4173<route> --app --out .plans/ui-redesign/taste/<theme>/<route>`. Run this with the theme set to light and to dark:
   - Set the theme via `localStorage['zsqc-theme']`. If the inspector can't preset storage, temporarily serve with a `?theme=` handled by the same pre-paint script. Allowed: the pre-paint script also accepts `?theme=light|dark` and persists it.
4. On Inspect, the inspector needs a result on screen: see the gotchas. Read every screenshot. Critique with taste-skill `references/critique.md`. Fix the top 3 problems and re-run, for at most 3 rounds.
5. Write `.plans/ui-redesign/taste/allow.md`, listing each remaining WARN → `--allow <rule>` + one-line reason. A known one is the cards in one row ending at different heights on Inspect, because the verdict card is intentionally taller.

### Phase 10: Record update
See Verification.

## Anti-Goals (Out of Scope)
- No backend/API change. Only the existing `GET /api/health` is newly read.
- No webcam capture, no launching eval runs, no Synthetic generate form.
- No UI kit, no icon font or icon package. `motion` and the two fontsource packages are the only new deps.
- No KPI tiles with tinted icon circles, no sparklines, no gradients, no emoji, no shadows on cards, no zebra tables.
- No fixing of the `data/synth/bottle/scratch` content: it shows cats, dogs and a portrait, which is a generator/data issue for a separate diagnosis.
- No changes to `docker-compose`, `Dockerfile` or `nginx.conf`.

## Edge Cases & Gotchas
- **Inline styles beat media queries.** The prototype overflowed at 768px for this reason. Put responsive grid templates in classes or Tailwind responsive variants, never in `style=`.
- **Icons widen the top bar.** At 768px the theme labels and health text must hide, or the page scrolls sideways.
- **Theme flash:** without the pre-paint script, a dark-theme user sees a light frame.
- **`localStorage` can throw** (private mode). Wrap it in try/catch and fall back to System.
- **Inspect's first screen in the gate has no result.** For the Inspect route, either run the inspector against the empty state (it must pass), or drive one inspection first if the inspector supports a script. At minimum, also verify the result state by a manual screenshot pass with the fake backend, inspecting `data/mvtec/bottle/test/broken_large/000.png` with profile `bottle`. Note that fake-segmenter boxes are scripted and don't land on real damage; that is expected.
- **Profiles without a reference image:** the Reference card must hold its size (aspect-square frame).
- **Box numbering:** a ruling whose `detectionId` has no matching detection still lists, without a box. Show "—" for its number.
- **`naturalSize`** must reset per result, or boxes from the previous image flash in.
- **The abort contract:** a new keystroke aborts the in-flight re-judge. Motion keyed on `result.id` must not replay for an aborted request.
- **The Eval ablation group must match on seed + source + sorted categories.** The `verify_*` and `m5verify-*` runs are separate groups.
- **The synth mask PNGs are tiny (48×48).** Scale them with `image-rendering: pixelated`.
- **The inspector flags `dev-server`.** Always gate against `vite preview`.
- **The `.lavish/` prototype references MVTec images.** Never `git add .lavish`.

## Navigation Anchors
- `frontend/src/App.tsx`: the shell and routes.
- `frontend/src/index.css`: all tokens.
- `frontend/src/pages/Inspect.tsx`: `runInspect`, the debounced `useEffect([rulesText])`, `handleFileChange`, `HoverBox`.
- `frontend/src/pages/Profiles.tsx`: `handleSaveEdit`, `handleDraftFromSop`, `handleSaveDraftAsNew`, `handleRefresh`.
- `frontend/src/pages/Eval.tsx`: `isFailure`, the `F1Bar`, and the failure viewer component.
- `frontend/src/pages/Synthetic.tsx`: the pair card component, and the grouping at line 81.
- `frontend/src/api.ts`: `getJson`, `resolveFileUrl`, and the new `getHealth`.

## Dependency Mappings
- New runtime deps:
  - `motion@^14.7.1` (`import { motion, AnimatePresence, MotionConfig } from 'motion/react'`; peers react ^18 || ^19);
  - `@fontsource/fira-sans`;
  - `@fontsource/fira-code`.
- Existing: react 19, react-router-dom 7 (`NavLink`, `useLocation`), tailwindcss 4 via `@tailwindcss/vite`, and vitest 5.
- Tools (not deps):
  - ui-ux-pro-max `search.py` (Python 3);
  - taste-skill `inspect.mjs` (Node + local Chrome over CDP).

## Phases
1. Design system (tokens, fonts, docs)
2. Primitives (`src/components/`, icons)
3. Shell (top bar, theme, health)
4. Inspect (prototype C)
5. Profiles
6. Eval
7. Synthetic (gallery only)
8. Motion pass
9. Taste gate loop
10. Record update (in Verification)

## Acceptance Criteria
1. `npm run build`, `npm run lint` and `npm test` pass in `frontend/`.
2. The taste inspector `--app` reports **0 FAIL** on `/`, `/profiles`, `/eval` and `/synthetic` at 1440/768/390, in light and dark, against `vite preview` + the fake-adapter backend. Each remaining WARN is listed in `.plans/ui-redesign/taste/allow.md` with a reason.
3. `grep -rnE '(bg|text|border)-(neutral|gray|red|green|amber|slate)-[0-9]' frontend/src/pages frontend/src/App.tsx frontend/src/components` finds nothing.
4. Each route renders exactly one `h1`.
5. Every flow still works against the fake backend:
   - inspect an image;
   - edit rules and see the verdict re-judge;
   - clear the rules to restore the profile rules;
   - save a profile;
   - draft from SOP;
   - open an eval run and a failure example;
   - view the synthetic gallery with masks.

   At 390px there is no horizontal scroll.
6. The theme switch persists across reload and overrides the OS. "System" follows the OS, and there is no flash of the wrong theme on load.
7. With the OS set to reduce motion, no element animates (`MotionConfig reducedMotion="user"` is present). Otherwise the verdict, rulings, boxes, tab underline and alerts animate as specified.
8. The built `dist/` contains Fira `.woff2` files and makes no request to `fonts.googleapis.com` or `fonts.gstatic.com`.
9. On Inspect, the Reference and Under test cards render side by side with a 12px gap at ≥1001px. A profile with no reference shows the "No reference set" frame. Hover or focus on a box highlights its ruling, and the reverse.
- manual: With real SAM/Muse keys in `.env` (`USE_FAKE_ADAPTERS=false`), inspect a real MVTec image. Check that the boxes sit on the actual defects and that the verdict card reads correctly.
- manual: `docker compose up --build`, open the frontend container URL, and check that the fonts load (DevTools → Network shows `.woff2` from the same origin) and that the theme switch works behind nginx.

## Test Strategies
| Phase | Check |
|---|---|
| 1 | `npm run build`. Inspect `dist/assets` for `.woff2`. Grep `dist` for `googleapis` (expect none). |
| 2 | Lint + typecheck. Eyeball primitives on the Inspect empty state. |
| 3 | `theme.test.ts`: `resolveTheme('dark'|'light'|undefined|'x')` gives dark/light/system/system, and `applyTheme` with throwing storage doesn't throw. `health.test.ts` (mock `fetch`): `{status:'ok'}` gives 'ok'; a 500 or network error gives 'down'; no throw. |
| 4 | `geometry.test.ts`: zero size gives null; `[90,180,90,45]` on 900×900 gives `{10,20,10,5}`. Browser: drop a PNG, Inspect, hover ruling #2 (box #2 highlighted), type rules (re-judge after ~500ms), clear (profile rules restored). |
| 5 | Browser: edit + save, Reload, SOP draft, save-as-new existing id (overwrite guard). |
| 6 | Browser: select `20261027T094406Z-sam_judge_ref`. KPIs show F1 0.919. The ablation panel lists 3 modes, and the 0.000 row is faint. Open a failure example. |
| 7 | Browser: filter chips change counts; Show masks toggles the overlay. |
| 8 | Browser with DevTools "Emulate prefers-reduced-motion: reduce": nothing moves. |
| 9 | The inspector matrix (16 runs: 4 routes × light/dark, each at 3 widths). |

Command: `cd frontend && npm run build && npm run lint && npm test`.

## Record Updates
- (frontend) The web app currently themes light and dark from one set of design tokens, following the system colour scheme unless the user picks a theme.
- (frontend) The web app currently self-hosts its typefaces and requests no third-party fonts.
- (frontend) The web app currently shows backend reachability in its top bar from GET /api/health.
