# TVA air programmes implementation plan

Use superpowers:executing-plans inline. Preserve the shared dirty checkout; no commits, worktree replacement, Computer Use or game launch.

**Goal:** Replace the cloned air-staff/temporary-bonus module with two air policies integrated into TVA's laboratories, network load and trained reserve.

**Spec:** docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md, TVA identity and common focus design requirements. Values below are implementation choices under the ongoing rework, not separately supplied lore.

**Architecture:** Existing TVA administration aggregate and programme receipt. Existing files per engine type; no new state currency, polling, aircraft archetype or lifecycle handler. Native existing CAS/fighter airframes match the starting TVA air force.

## Contract

Retire TVA_stand_up_the_grid_air_staff after tracing consumers. The two surviving mutually exclusive focuses directly require TVA_deploy_field_laboratories, cost 21 days, and stay at cells (63,9)/(65,9). They require active TVA administration, not an already available stockpile. The programme itself checks productive facilities and capacity. Both political courses may choose either air policy. No military readiness focus depends on them.

- TVA_print_unattended_strike_packages is renamed to network-guided strike aviation. Its existing idea becomes a dummy preview: +8% CAS mission efficiency and +6% air accidents, applied to TVA_policy_air_cas_efficiency / TVA_policy_air_accidents_factor in TVA_administration_dynamic. It opens TVA_strike_aircraft_programme.
- TVA_keep_the_interdictors_on_station retains interceptor identity. Its existing idea becomes a dummy preview: +10% interception efficiency and +8% range, applied to TVA_policy_air_intercept_efficiency / TVA_policy_air_range_factor. It opens TVA_interceptor_reserve_programme.
- Strike programme: 40 PP, 120 support equipment, 300 manpower; 21 days; receipt kind 7. Delivery gives 24 ADISCORD_cas_airframe_2170, adds 20 network load and spends 10 cadre reserve. Current load must be <=65 and cadre >=25 at payment and delivery.
- Interceptor programme: 40 PP, 100 support equipment, 200 manpower; 28 days; receipt kind 8. Delivery gives 30 ADISCORD_fighter_airframe_2163, adds 10 load and spends 5 cadre. Current load <=80 and cadre >=20 at payment and delivery.
- Both need an owned/controlled airbase and an owned/controlled military factory (possibly different states), the relevant completed focus and active independent administration. They remain usable between regional wars, until the civil conflict's terminal outcome. They share TVA_programme_pp/support/manpower/kind with all existing operations. Exact fractional affordability, one debit, full cancellation refund, paid successor handoff and inert wrong-kind/repeated callbacks are mandatory. No free reactivation decision remains.
- Policy modifiers are wartime administration policy, not installed timed ideas. Variables initialize once, survive current-campaign subjugation/liberation and cease affecting a successor when the wartime administration closes. All four previews equal applied deltas. Paid undelivered aircraft orders refund the successor through existing callers.
- Use inspected action icons with matching shine masks. Narrative descriptions do not duplicate mechanics. Compact costs show number then texticon. RU/EN BOM, scripts without BOM, ASCII punctuation and tab-indented authored blocks.

## Tasks

- [x] Add source-executing tests for payment boundaries, shared capacity, material aircraft, network/cadre limits, facilities and political lifecycle, handoff and exact aggregate previews. Observe RED before implementation.
- [x] Implement the programmes and aggregate fields, rewrite focuses/localisation/icons and remove retired head, duplicate flags and free activation decisions. Preserve existing aircraft data.
- [x] Update explicit manifests, AI routes and source geometry; check/apply/check and prove idempotence. Inspect action textures and source layout; remove only owned previews.
- [x] Run Vorkerland and shared callback tests, full TC, BOM/diff checks. One fresh read-only review; resolve material findings with RED/GREEN. Record native verification limits.

## Review focus

Capacity may change during paid production; a completed order must recheck both facilities, cadre and network values. Lost independence or the end of the civil war must refund every currency and never deliver airplanes afterward. A wrong receipt kind must not consume another programme. Both choices need real usable airframes already supported by TVA's air force, not future equipment without a mission. The focuses must remain reachable under both political mandates without repeating earlier policy rewards, and aggregate preview values must match live effects before the engine records focus completion.
