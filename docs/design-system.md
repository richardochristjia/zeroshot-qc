# Design system

Swiss minimal, Fira Sans + Fira Code (bundled via fontsource, no CDN). Colour appears on data only. Tokens live in `frontend/src/index.css` in three layers: primitives (raw scales), semantic (light), and dark (applied by OS preference unless `data-theme="light"`, or forced by `data-theme="dark"`). Tailwind v4 `@theme inline` maps them to utilities: `bg-surface text-ink border-line text-fail`.

## Tokens

| Token | Use |
|---|---|
| `ground` / `surface` / `sunken` | page / cards and bars / hover, selected, inset |
| `ink` / `ink-2` / `ink-3` | text: primary / secondary / hint |
| `line` / `line-strong` | hairlines / control borders |
| `accent` / `on-accent` | primary button, brand mark |
| `pass` / `pass-tint` | pass verdicts, cleared |
| `fail` / `on-fail` / `fail-tint` | fail verdicts, defects, errors |
| `detect` | candidate boxes |
| `data` | chart bars, selected series |
| `focus` | focus ring |

Radii: `--r-sm` 4px, `--r-md` 6px. Transition: `--dur` 160ms.

## Type scale

| Role | Size / weight |
|---|---|
| Page title (`h1`) | 20px / 600 |
| Section (`h2`) | 13px / 600, `ink-2` |
| Body | 14-15px / 400, line-height 1.5 |
| KPI | 26px / 500, tabular |
| Mono (ids, paths) | Fira Code 13px |

## Spacing

4px grid. Common gaps: 4, 8, 12, 16, 24. Page max width 1360px, 20px gutter.

## Rules

- Colour on data only; chrome stays neutral.
- No shadows on cards, no gradients, no zebra stripes.
- Numbers are right-aligned and tabular (`.num`).
- No icons on KPIs.
- One `h1` per page (`PageHeader`).
- Buttons: 36px tall, 44px on coarse pointers. Focus ring is global (`:focus-visible`, 2px `focus`).
- Icons come from the inline sprite (`Icon`), 24px viewBox, stroke 1.8.
