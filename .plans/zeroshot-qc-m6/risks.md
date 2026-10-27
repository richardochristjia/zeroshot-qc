# ZeroShot QC — M6 risks (Phase 1 code check)

- Starlette `StaticFiles` may normalize or pass through `..` segments in `/files/...` paths on its own; the traversal test must prove the block with the real mounted app, adding an explicit guard if the framework alone 404s unreliably.
