# Taste gate: allowed WARNs

Inspector `--app`, 4 routes x light/dark x 1440/768/390: 0 FAIL on all 8 runs. Remaining WARNs:

- palette-cream (light, all routes): ground #f6f5f1 is the chosen warm stone token (docs/design-system.md); low chroma, deliberate product identity.
- hero-void (Inspect, 1440): empty-state view. Below the drop zone and rules panel there is nothing until an image is run; filling it with invented content would be a placeholder. Closes as soon as a run exists.
- panel-void (Inspect, 1440): drop zone and rules panel stretch to the same height in a two-column grid; 42-49px of padding, intended to keep the frame.
- ragged-row (Profiles, Eval, 1440): list panel beside an editor/detail panel of different length; they are different blocks, aligned at the top on purpose.
- tiny-text (Synthetic): 12px card captions and tags (category / #id); secondary metadata, above the 11px floor.
