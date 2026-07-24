# Vorkerland Runtime Repair and Flags Design

## Goal

Make the Vorkerland collapse load cleanly in Russian, spawn valid OOBs, avoid scope errors, monitor outcomes efficiently, and document which sixteen tags need user-supplied flags.

## Runtime design

- Russian localisation uses UTF-8 BOM and double-quoted HOI4 values.
- Collapse OOBs use ordered division-name blocks accepted by HOI4 1.19.
- The startup dirty-state effect executes inside the stable RUS country scope.
- A hidden RUS event checks the three victory candidates every 14 days while the collapse is active. Seven successful checks equal the existing 98-day continuity requirement. The global weekly country pulse is removed.

## Flag handoff

The implementation does not replace flag assets. The handoff lists the sixteen tags and the three standard HOI4 flag directories so the user can supply final artwork.

## Verification

Automated tests verify parser-safe localisation, valid OOB naming, a scoped startup effect, the absence of Vorkerland weekly polling, and the 14-day recursive monitor.
