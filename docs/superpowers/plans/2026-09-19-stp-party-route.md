# Stelander party route implementation plan

**Goal:** Make the party an independent campaign from succession to reconstruction, preserving Shabrat and deferring internal-party Balance of Power.

**Architecture:** Extend the canonical STP focus, decision, effects, scripted-localisation, idea and AI-plan files. Existing loyalty, election mandate, district assets, shared resource accounting and recovery receipts remain authoritative. No new recurring pulse or duplicate gauge.

## Delivery units

1. Side-aware election and map briefings. Add complete party/resistance selectors; keep resistance wording. Reproduce mixed-side guidance with `PartyRouteContracts.test_entire_election_briefing_switches_side`.
2. Preparation. Uncouple basic administration and Congress defence from fiscal specialization. Move the security response early enough for the first announced operation. Offer negotiated district appointments versus emergency rotation, with an OR join into the presidium. Add six focuses for treasury, arsenals, district records, supply and succession. Verify both budget paths and both district paths using graph reachability.
3. Civil war. Add rear administration, transport and operational command. Replace the silent assault-spawn reward with a repeatable fully priced order using the existing payment/deployment helpers; maintain the fixed template and exact affordability contract.
4. Postwar. Extend the two existing settlements by two focuses each, then join at the civil charter. Add an income/credit/tax and industrial program plus two research focuses. Keep protection versus sovereignty independent of domestic policy. Use exact dummy deltas and existing country aggregates; always invalidate the economy cache.
5. Lifecycle and presentation. Guard all delayed election deltas, district ownership/controller checks and changing foreign prerequisites. Add three bounded narrative events with no duplicate mechanical settlement; register IDs. Add party AI plans without rewriting Shabrat plans.
6. Verification and publication. Run `python -B -m unittest tools.tests.test_adiscord_stp_party_route -v`, compare all STP tests to the same base, run `python -B tools/validate_tc.py --limit 300` on the complete checkout, inspect `git diff --check` and asset references. Publish only explicit gameplay/test/doc paths onto the current main ancestry, without workbench files. Record pre-existing failures separately; static checks do not replace a native cold-load campaign.

## Constraints

Russian localisation: UTF-8 BOM, one physical line per value. Scripts: UTF-8 without BOM. Existing focus IDs and Shabrat payloads are preserved. Party political modifiers stay with STP; only the existing resistance pending variables pass to STS. No external country's stock is debited without its existing acceptance flow. New order code must use existing payment predicates and receipts, not an additional source of truth.
