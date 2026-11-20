---
name: responsive-hud
description: Turn one supported game's three-region design handoff into a reviewable responsive HUD proof and inspect measured failures.
---

Use the current game's studio/hud-brief.json. Verify every binding resolves to its declared game source and keep the acceptance key out of inference prompts. When a component changes, update its source binding and design text in one review.

1. Run the game's Responsive HUD handoff workflow or the local commands in the shared [workbench](../../../studio/hud/README.md).
2. Open screen.html and check the acceptance evidence. In authoring.json, distinguish first-choice model results, rejected candidates and forced singleton assignments.
3. Inspect the viewport either side of the breakpoint, short landscape, action size and computed palette. Both the swapped semantic bindings and the small target should trigger failures in their respective controls.
4. For a reported mistake, add a fresh paraphrase to the game evaluation set. Run the same inference route and lexical baseline on it. Keep previous misses in the evidence.
5. Link the game revision, workflow result and relevant measurement in the game report. For team-time claims, attach a consented, paired human observation with task order and rework. Developer-tool timings are available independently in the JSON artifacts.
