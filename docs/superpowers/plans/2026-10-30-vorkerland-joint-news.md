# Joint government news completion plan

Use superpowers:executing-plans inline. Preserve the shared dirty checkout; no commits, worktree replacement, Computer Use or game launch.

**Goal:** Keep the joint cabinet's news coherent with its actual succession outcome, including observers.

**Spec:** docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md, VAD joint cabinet and imperial succession.

**Architecture:** Keep the existing events, guarded transitions and founder predicate. Extend the existing scripted localisation for the proclamation response. The caller owns once-only dispatch; major news must permit fan-out. No new story state, recurring work or generated outputs.

## Contract

- The existing joint cabinet pair and news 44-47 remain intact. The default succession response preserves the cabinet; an explicit coup retires Petrichev and announces his execution.
- News postwar.5 uses the same WRK-scoped founder for title, description and response. An observer's own ruler must not change its response. The Petrichev proclamation cannot describe his death.
- Set postwar.5 to fire_only_once = no, matching the existing story-news contract. Both guarded transition callers remain idempotent. The broadcast itself has no gameplay mutation.
- Preserve all narrative prose, correcting only the inconsistent spelling of Petrichev in the Russian coup description. Add RU/EN response variants with UTF-8 BOM and one physical line per value.
- Extend the existing postwar tests with actual transitions, response selection in WRK scope for domestic and foreign recipients, and broadcast-safe acknowledgement. No focus or generator changes.

## Tasks

- [x] RED: regression tests in tools/tests/test_adiscord_vorkerland_vad_postwar.py for proclamation response and broadcast. Expected failures: missing founder response and fire_only_once = yes.
- [x] GREEN: update the existing events, scripted localisation and RU/EN country localisation. Update the founder-localisation inventory and existing guide's news contract.
- [x] Run joint programme, postwar and story tests, then the full Vorkerland source suite, validate_tc.py --limit 300, BOM checks and git diff --check.
- [x] One fresh read-only review; one author fix pass for material findings. Runtime fan-out, event rendering and actual timeout handling remain manual.

## Review focus

Check both empire founders, foreign observers, the preserved joint-cabinet outcome, repeated transition calls and stale succession choices. Verify that enabling news fan-out does not introduce duplicate dispatch or repeat gameplay effects. Check complete quoted localisation and preservation of prose. Native multiplayer news delivery and event rendering are not proven by source tests.
