# The Record

A curated list of factual, scoped statements asserting the application's **current** state. Authoritative for the present, never the future.

The planner consults this file before proposing a plan. If a feature **contradicts** an entry here, the contradiction is surfaced before the plan proceeds. If a feature **establishes a new high-level fact**, a verbatim entry is proposed for human approval as part of the plan. You may edit the RECORD, but only after presenting the changes to a human and getting human approval.

## Why This File Exists

A planner reads this file _instead of_ reading the code, so an entry earns its place only by being **expensive to re-derive** — a decision, a boundary, a user-visible behavior, or a fact whose only copy is scattered across several files.

If a reader could recover the fact from one grep or one file read, it does not belong here. Most things do not belong here. The list is expected to be short, and adding an entry is a claim that the fact is not already obvious from the code.

Deleting an entry is always safe; a planner that needs it will find it. A record that grows to mirror the codebase costs every future planner and goes stale within weeks.

## Format Rules

- **Factual.** Assert how things are _now_. Never future intent ("we will...", "should..."). Each entry is the current state of the application.
- **Durable.** Every entry must survive a routine change. Apply the **rename test**: if the codebase renamed this thing tomorrow — a config key, a crate, a type, an actor, an event, a schema version — would the entry be false? If yes, it is not a fact about the application; it is a fact about today's source tree. Delete it.
- **Scoped.** Name what each entry applies to — repo, app, frontend, or a named subsystem. An unscoped fact (e.g. "uses Fossil") is ambiguous: is that the repo, or the app's supported VCS list? Always disambiguate.
- **High-level.** One-liners (a few sentences at most). Capture decisions and facts a planner needs, not implementation minutiae.
- **Single tag.** Each entry carries exactly one subsystem tag as a `(tag)` prefix: `- (tools) The bash tool runs...`. One entry, one tag — this keeps tag usage a meaningful coverage metric (a tag growing large signals over-specification or a tag that should split). If you cannot decide between two tags for an entry, that is a signal to **re-evaluate the entry itself**, not to assign both. Use `(tag)` rather than `[tag]` to avoid colliding with markdown task-list (checkbox) syntax.
- **Tag subsystem scope.** It's not always obvious what tag to use for a given record entry. Pick based on existing tags or somewhat related subsystem. As particular tags start to become numerous, evaluate whether a new tag (subsystem) should be created based on the content of the tags. It's normal for subsystems to form after-the-fact so feel free to propose re-tagging of existing records.
- **Singular concept.** Each entry should be a single sentence and only concerned with a single concept. Prefer multiple entries versus combining many things into one.

## Templates

| Pattern     | Form                                                             | Example                                                                                             |
| ----------- | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| State       | `[Scope] currently [does X / is Y].`                             | "(TUI) The TUI's first screen at startup is the chat screen."                                       |
| Persistence | `[Scope] persists [what] to [where].`                            | "(sessions) Sessions persist to SQLite."                                                            |
| Flow        | `[Input/event] is handled by [actor/subsystem], which [action].` | "(tools) File edits route through the `edit` tool, which requires a unique match or `replace_all`." |
| Boundary    | `[Scope] is bounded by [constraint].`                            | "(projects) Project discovery walks ancestors until a VCS root or `$HOME`, whichever comes first."  |

## Absence

A missing record, or an un-recorded area, simply means the list has no entry there yet. Absence is not a constraint — it is an open question, and a feature that fills a gap may establish the first entry for that area (proposed for human approval as part of the plan).

## Editing

Entries are added or amended **only with human approval**.

---

- (pipeline) Inspection currently routes segment and judge model calls through a disk cache keyed by a hash of their inputs.
- (adapters) Model access currently goes through Segmenter, Judge, and ImageGenerator protocols with fake implementations for tests.
- (config) Model IDs are currently read from environment configuration and never hardcoded.
- (data) The data directory currently holds datasets, cache, and run outputs and is excluded from version control.
- (pipeline) Segmentation currently filters detections by profile min_score and merges duplicates with IoU above 0.5.
- (pipeline) Detection sizes are currently measured in pixels and converted to millimetres when the profile sets mm_per_px.
- (judge) Inspection currently judges detections against plain-English rules and a reference image, retrying once on schema failure.
- (judge) A rules override currently replaces the profile rules for a single inspection run only.
- (pipeline) A FAIL verdict is currently forced in code when any ruling cites a violated rule or any missed defect exists.
- (eval) Eval currently samples 10 good plus 20 defective images per category with a fixed seed and scores precision, recall, F1, accuracy, AUROC over the fail score, and pixel IoU on defectives.
- (eval) Ablation modes currently differ only in judge wiring: any-detection FAIL without a judge, judge without a reference image, and judge with the category reference image.
- (eval) Eval runs currently persist per-image results.jsonl plus a summary.json of per-category and overall metrics under data/runs/{run_id}.
- (synth) Synth generation currently writes deterministic image+mask pairs under data/synth/{profile}/{defect}/, storing exact generator masks verbatim and deriving missing ones by image-diff threshold.
- (eval) Eval currently accepts --data synth to score synthetic pairs through the same sampler, metrics, and ablation modes as MVTec.
- (profiles) New profiles are currently draftable from an SOP paragraph via POST /api/profiles/from-sop, which persists nothing and returns 422 when validation fails twice.
- (api) Inspection requests are currently served by FastAPI routers with images served from data/ under /files/.
- (frontend) The web app currently offers Inspect, Profiles, Eval, and Synthetic pages against the backend API.
- (frontend) The Inspect page currently re-runs only the judge when rules change, reusing cached segmentation.
- (frontend) The Eval page currently displays existing runs and never launches new ones.
- (frontend) Image upload is currently file-based without webcam capture.
