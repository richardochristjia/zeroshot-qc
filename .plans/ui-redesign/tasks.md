## Design system
- [x] Run ui-ux-pro-max design-system, stack and ux queries; read taste-skill references/app-screens.md
- [x] Add motion, @fontsource/fira-sans, @fontsource/fira-code to frontend/package.json
- [x] Write primitive/semantic/dark tokens and @theme mapping in frontend/src/index.css; import fonts in main.tsx
- [x] Write docs/design-system.md (tokens, type scale, spacing, rules)

## Primitives
- [x] Create Icon sprite + Icon component with the prototype icon set
- [x] Create Button, Field, Panel, Alert, VerdictBadge, PageHeader, EmptyState in frontend/src/components/
- [x] Add global focus-visible ring and touch-target sizing

## Shell
- [x] Add theme.ts (resolveTheme, applyTheme) + pre-paint theme script and color-scheme meta in index.html
- [x] Add getHealth() to api.ts and HealthDot component (30s poll, never throws)
- [x] Rebuild App.tsx top bar: reticle mark, icon tabs, health dot, ThemeSwitch; responsive wrap; one h1 per page
- [x] Replace public/favicon.svg with the reticle mark
- [x] Add theme.test.ts and health.test.ts

## Inspect
- [x] Extract boxPercent into geometry.ts with geometry.test.ts
- [x] Rebuild Inspect header run bar with drag-and-drop drop zone
- [x] Build empty state (drop target + profile rules/prompts panel)
- [x] Build Reference + Under test preview cards (12px gap) with legend and no-reference frame
- [x] Build verdict card (badge, summary, numbered rulings, timings, rules override) keeping debounce/abort behaviour
- [x] Wire box <-> ruling hover/focus linking and defect/cleared colouring

## Profiles
- [x] Rebuild Profiles list + editor + save bar on primitives, keeping all save/refresh flows
- [x] Rebuild SOP draft panel with overwrite guard, keeping all logic

## Eval
- [x] Rebuild runs list with friendly mode names and tabular F1
- [x] Build run panel: KPI dl, confusion line, right-aligned tabular category table with F1 bars
- [x] Build ablation panel grouped by source + seed + categories
- [x] Restyle failure examples list + viewer with empty states

## Synthetic
- [x] Rebuild gallery as filter chips + card grid with Show masks overlay (no generate form)

## Motion
- [x] Wrap app in MotionConfig reducedMotion="user"
- [x] Animate verdict card, staggered rulings, box draw-in and re-judge crossfade
- [x] Animate route fade, tab underline layoutId, synthetic grid layout, AnimatePresence alerts/SOP preview

## Taste gate
- [x] Run fake-adapter backend + vite preview; run inspector on 4 routes x light/dark x 1440/768/390
- [x] Look-and-fix loop up to 3 rounds against references/critique.md
- [x] Write .plans/ui-redesign/taste/allow.md with every remaining WARN and reason

## Verification
- [x] AC1: npm run build, npm run lint, npm test pass in frontend/
- [x] AC2: inspector 0 FAIL on 4 routes x 3 widths x light/dark; WARNs listed in allow.md
- [x] AC3: grep for raw neutral/gray/red/green/amber/slate palette classes in pages, App.tsx, components finds nothing
- [x] AC4: each route renders exactly one h1
- [x] AC5: all flows (inspect, re-judge, clear rules, save profile, SOP draft, eval run + failure example, synthetic masks) work against fake backend; no horizontal scroll at 390px
- [x] AC6: theme switch persists across reload, overrides OS, System follows OS, no wrong-theme flash
- [x] AC7: reduced motion stops all animation; otherwise specified animations play
- [x] AC8: dist/ has Fira .woff2 and no fonts.googleapis.com / fonts.gstatic.com requests
- [x] AC9: Inspect Reference + Under test side by side with 12px gap at >=1001px; no-reference frame; box <-> ruling linking both ways
- [x] Record Updates: (1) review the complete implementation; (2a) if it matches the planned Record Updates in plan.md, write those exact entries into .agents/RECORD.md; (2b) if it diverged, do not write a wrong entry — surface the divergence in the final summary

## Manual checks
- [ ] manual: with real SAM/Muse keys (USE_FAKE_ADAPTERS=false), inspect a real MVTec image; boxes sit on actual defects and verdict card reads correctly
- [ ] manual: docker compose up --build; fonts load from same origin and theme switch works behind nginx
