# Kefreyt feedback implementation plan

> **For agentic workers:** Execute with superpowers:executing-plans. Preserve unrelated working changes; do not commit or deploy.

**Goal:** Make recruitment, regional investment and scripted territorial rewards bounded and understandable.

**Architecture:** Extend existing country files and the shared national-project system. Keep native project factory allocation, state-owned construction receipts and the existing frontier campaign lifecycle.

**Tech Stack:** Clausewitz scripts, UTF-8 BOM localisation, Python generators and unittest.

**Spec:** User-approved seven-point proposal in this chat, with installed TFR as a structural reference.

## Constraints

- Existing gameplay and localisation files remain grouped; generated technology is changed through its builder.
- No old-save migration, global combat-damage rebalance, commit or deployment.
- Preserve concurrent STP edits.
- Static tests do not establish native loading or campaign balance.

## Work

- [x] National projects: project-available factories, exact three-factory reservation, completion/cancellation release.
- [x] Recruitment: local reserve pays for recruitment; national intake uses a paid preparation period with refunds on cancellation.
- [x] Frontier workshops: two paid stages, second stage costs 1000 and requires infrastructure, state receipts preserve parallel work and refunds.
- [x] Construction: moderate shared-slot bonuses in existing reconstruction technologies, regenerated and checked twice.
- [x] Tsaygen: one frontier campaign for direct war and ultimatum, blocked alternate launch, settlement before unrelated annexation.
- [x] North: verify and repair final capitulation reservation across every native callback.
- [x] Presentation: honest chapter completion and explanation of BOP consequences; preserve story prose.
- [x] Verification: focused regression tests, full validator, diff/encoding checks and final independent review.

## Review focus

- A second workshop cannot overwrite an existing receipt; cancellation returns the actual paid price.
- Recruitment cannot consume the same reserve twice or lose paid reserves on cancellation.
- Filled construction queues do not prevent a project, and completed projects release all reservations.
- A foreign capitulator does not erase the already occupied Tsaygen claim.
- The last northern capitulation does not fall through to ordinary annexation after settlement clears campaign flags.

## Acceptance boundary

Native price rendering, construction queue allocation and campaign outcomes require a fresh game. Combat damage and AI policy remain unchanged until comparative campaign evidence identifies a defect. No runtime acceptance is claimed.
