# A-Discord Recovery Design

**Date:** 2026-08-08
**Status:** Approved in conversation
**Scope:** Vorkerland civil war, regional wars, military AI and balance, economy/UI, repository inventory, tooling, and technical internationalisation

## 1. Objective

Recover A-Discord from a statically validated but unreliable state. The result must be understandable to a maintainer, observable to a player, performant enough for normal play, and proven in fresh HOI4 campaigns rather than only by text validators.

The central Vorkerland war is the release gate. It should normally take two to three in-game years, produce meaningful movement every 60-120 days, allow several plausible winners, use aircraft, and avoid both permanent inactivity and suicidal two-province wars.

Large scripted effects are acceptable when they have a clear entry point, scope, state transition, terminal result, and tests. File size alone is not a defect. Hidden global or weekly polling, silent event loss, unbounded retries, and duplicated responsibilities are defects.

## 2. Non-goals

- Do not create a full English translation of unfinished legacy content.
- Do not copy TFR, TDA, or Expert AI wholesale.
- Do not consolidate engine-required state, map, or generated files only to reduce the file count.
- Do not guarantee a scripted winner or resolve stalemates through arbitrary white peace.
- Do not give the AI unlimited units, free technology, immunity to inflation, or large direct combat bonuses.
- Do not push commits without a separate request.

## 3. Reference principles

TFR is a reference for prepared tags, explicit war topology, regional militia decisions, state-control reactions, regional coring, and dedicated AI strategies. TDA is a reference for economy information architecture, separate research spending, actionable tooltips, notifications, and bounded AI assistance. Expert AI is only a pattern library for force-design and front priorities.

References are behavioral examples, not permission to import overlapping `replace_path` systems or their numerical scale.

## 4. Civil-war identity and phases

### 4.1 Tag semantics

`WRK` is the reunified, postwar Vorkerland tag. It is not a wartime claimant.

The central war uses:

- a new temporary Worker-loyalist claimant tag, `WKR`;
- `VAD`;
- `TVA`.

When a central route wins, the winner forms or transfers into `WRK`. The temporary claimant tags retire. The route determines the leader, government, ideas, and political branch of reunified Vorkerland.

A joint Worker/VAD government forms `WRK` under a compromise leader and cabinet. It is never implemented as VAD annexing WRK.

### 4.2 Phase controller

The war is an explicit state machine:

1. **Prewar preparation.** Focuses and a visible event establish political support and AI route weights.
2. **Collapse.** The central claimant tags and regional actors receive their prepared territories, armies, claims, and home cores.
3. **Regional consolidation.** Each central claimant attacks only assigned neighbors or proxies. VAD can support the Solyarino loyalists; TVA can use technocratic proxies.
4. **Central preparation.** Claimants fill fronts, stockpile supplies, deploy air wings, and receive visible preparation decisions.
5. **Central showdown.** Surviving claimants fight each other through explicit, bounded war-launch effects.
6. **Reunification.** The winner becomes `WRK`; defeated temporary claimants retire.
7. **Postwar integration.** Shared military, economic, recovery, and coring content opens, together with the chosen political route.

Every phase has one authoritative flag. A success flag is set only after the associated result has actually occurred. Diplomatic-cache or faction-detachment retries are bounded and leave a diagnostic flag and log entry if they fail.

## 5. Regional wars and outcome matrix

ROM, TRU, VAL, and the northern ZAO theater are independent political and military systems. A regional victory does not automatically turn its winner into a WRK puppet.

The postwar relationship is selected from an explicit matrix:

`regional winner x reunified WRK regime -> outcome`

Supported outcomes are:

- full independence;
- mutual guarantee or non-aggression pact;
- military alliance;
- economic or political association;
- voluntary confederal autonomy;
- forced subject status;
- a later reunification war.

The exact result depends on the specific winner, not only on the geographic region. For example, a ZAO victory may unlock negotiated return, while WPA, WPS, PSD, or PWR victories may produce different results. VAL's wartime contract or support choice does not imply automatic postwar subjection.

The matrix is stored in a single documented source and validated for complete coverage. No generic `puppet` fallback may silently absorb every regional survivor.

Minimum canonical commitments are:

- a ZAO victory is eligible for a voluntary confederal-autonomy offer, never automatic subjection;
- other northern winners remain sovereign by default unless their own route explicitly accepts a central patron;
- the winner of the ROM/DVA and TRU/ZTA regional contests remains sovereign by default; WRK may offer an alliance, guarantee, or later confrontation;
- VAL remains a sovereign contractual partner by default; choosing a central recipient for wartime support does not waive that sovereignty;
- any exception that creates a subject must name the regional winner, the compatible WRK route, and the player-visible consent or coercion event.

## 6. Focus and decision structure

### 6.1 Wartime claimants

WKR, VAD, and TVA receive short phase-oriented trees:

- stabilize the regime;
- organize the army and repair templates;
- secure allies and proxies;
- consolidate the local region;
- prepare the central front;
- conduct the showdown;
- take emergency defensive measures;
- form reunified Vorkerland.

The route is not chosen by naked randomness. The player receives an explicit event or focus choice. AI weights come from prewar focuses, faction support, supported proxies, ideology, and actual war results.

### 6.2 Reunified WRK

All political routes share:

- army development;
- air and naval development;
- economy and science;
- war recovery and debuff removal;
- infrastructure reconstruction;
- regional integration and coring.

The political component is mutually exclusive. Approved routes include the Worker government, joint government, and utilitarians. Additional routes require distinct conditions and content rather than cosmetic leader swaps.

### 6.3 Repeatable decisions and political-power sinks

Repeatable decisions are allowed when bounded by cost, cooldown, regional availability, and a capped result. Useful AI sinks include:

- frontline propaganda;
- regional agitation;
- volunteer recruitment;
- weapon collection;
- proxy-loyalty campaigns;
- integration preparation;
- discrediting a rival claimant.

AI priority is: mandatory story and military actions first, then bounded propaganda or administrative spending when political power exceeds a reserve.

## 7. Militia and defensive escalation

TFR's Trump/USC defensive-line decisions are a structural reference. A-Discord uses its own scale and correct conditions.

- Major defensive lines and last-stand mobilizations are `fire_only_once`.
- Local volunteer mobilization may repeat with a default 90-day cooldown and a regional quota. A different cooldown requires a documented balance reason.
- Decisions require a controlled, supplied, non-encircled spawn state.
- Militia consumes manpower, infantry equipment, and political power.
- Weak militia starts with low experience and approximately 25-40% equipment.
- Better reservists cost substantially more and do not receive intentionally low equipment.
- Excess mobilization accumulates economic strain, stability loss, or war exhaustion.
- AI takes these decisions only during real retreat, exposed fronts, or insufficient defensive density.

Militia prolongs a losing front; it must not create an infinite unit stream or become the best offensive template.

## 8. Dirty-zone opening

The dirty zone remains closed for exactly 1095 days after the Vorkerland collapse. A persistent one-shot schedule then fires the opening superevent and materialises SLA, MLR, RZA, SCA, ERT, and IRT one at a time over the following 11 days so ownership, supply, and front caches can settle between countries.

The legacy 60–90-day reveal event remains defined only as a no-op so serialized old timers cannot open the zone early. An unopened old save receives one new 1095-day schedule on startup; an already opened save is never rolled back. There is no monthly world poll.

## 9. Coring and integration

- Temporary claimants core only their genuine home territory.
- Absorbed neighbors and proxies remain claimed or occupied during the war.
- Reunified `WRK` integrates explicit regional packages through shared focuses and decisions.
- Integration requires control, time, political power, and acceptable resistance or compliance.
- Voluntary confederal entrants use a cheaper and faster path.
- Forced conquests use a longer and more expensive path.
- Independent allies do not receive WRK cores and do not grant their territory as WRK cores.
- Blanket `every_owned_state = { add_core_of = ROOT }` behavior is prohibited.

## 10. Map, population, victory points, and supply

Map expansion is targeted at the central and northern theaters.

- Split states that produce one- or two-province fronts or prevent useful maneuver.
- Add ordinary settlement victory points and distribute value beyond capitals.
- Increase population where factions cannot sustain the intended force density.
- Audit capitals, supply sources, railways, infrastructure, hubs, and air bases.
- Preserve generated ownership: modify builders and manifests, regenerate, and validate outputs.

The target is enough space and force density for movement without creating a TFR-sized global tag explosion.

## 11. Division-template and OOB audit

Every active civil-war template receives a machine-readable audit row containing:

- ASCII/English technical and displayed name;
- battalion and support-company composition;
- organization with the country's starting technology;
- manpower and full equipment cost;
- availability of every required equipment archetype;
- starting equipment and experience factors;
- supply consumption;
- intended AI role;
- AI upgrade and replacement path;
- every OOB and scripted `create_unit` reference.

Line and territorial units must have enough organization to move and fight. Low experience and low equipment are reserved for deliberately weak militia. OOB quantities are balanced only after template costs, available stockpiles, front width, and supply have been calculated together.

Cyrillic technical template names are replaced atomically in generator sources, generated OOBs, history files, and scripted unit creation.

## 12. Military AI and anti-stall behavior

AI strategies are phase-specific:

1. **Consolidation:** one assigned target; avoid opening parallel suicidal wars.
2. **Preparation:** cover the front, recover organization, stockpile, and deploy aircraft.
3. **Offensive:** prioritize a concrete route and meaningful victory points.
4. **Recovery:** pause briefly after severe losses rather than repeatedly attacking at zero organization.
5. **Final struggle:** surviving central claimants switch to the showdown strategy.

A visible 90-day initiative mission tracks significant progress. Capturing a meaningful state or victory point refreshes it. Expiry first grants a bounded planning, supply, or organization-recovery intervention; later expiry can unlock emergency mobilization or a prepared offensive. War exhaustion grows during prolonged inactivity. The system never assigns a winner or forces an arbitrary white peace.

Acceptance targets:

- central war normally ends in two to three years;
- meaningful movement at least every 60-120 days;
- no central claimant wins an overwhelming majority of observer campaigns;
- northern fronts do not remain unchanged for years;
- emergency measures do not create infinite divisions.

## 13. Air and technology data flow

Aircraft availability and aircraft employment are separate contracts. Validation follows the full chain:

`starting technology -> valid variant -> stockpile -> air-base capacity -> fuel -> air wing -> strategic region -> active mission`

The claimant setup creates only valid aircraft and wings. Each phase assigns AI priorities to reachable strategic regions. Weekly forced spawning or redeployment is removed. One-time setup, war/focus events, and normal AI strategy must produce actual active missions after a full restart.

## 14. Economy schema

### 14.1 Player regulators

The economy exposes exactly four five-level policies:

- taxation;
- military spending;
- research and science spending;
- social spending.

Construction spending is automatic and based on real construction activity. It is not a player policy.

Schema migration maps the old construction-policy level to research spending, removes obsolete construction-policy ideas, preserves treasury, debt, and accounting history, refreshes signatures, and allows the player to change the new policy without being trapped by an inherited cooldown.

Research policy levels range from austerity penalties through a neutral middle to positive research investment. Only level five receives a small construction-speed bonus, targeted at `+2%` and capped at `+3%`.

### 14.2 Debt model

There is no separate debt-capacity statistic.

- A negative treasury automatically borrows only the uncovered amount.
- Debt creates weekly interest expense.
- Debt pressure is derived from debt, interest share, income, and persistent deficit.
- Repayment immediately reduces interest.
- Sustained critical conditions can cause default, but one threshold crossing does not cause instant bankruptcy.

Debt states are:

- **fiscal strain:** weekly interest is at least 10% of weekly gross income;
- **debt crisis:** weekly interest is at least 25% of weekly gross income;
- **budget emergency:** weekly interest is at least 40% of weekly gross income for four consecutive settlements;
- **default:** budget emergency persists together with a negative weekly balance for thirteen consecutive settlements.

Each tier applies a visible, reversible debuff. The first automatic loan and each upward tier transition produces a player notification containing the cause, current debt, interest, and next risk. Routine weekly borrowing does not spam popups. Dropping below a tier removes or reduces the debuff; a later genuine deterioration may notify again.

### 14.3 Modest AI assistance

AI assistance compensates for management weaknesses without replacing the economy or deciding wars.

Default bounds are modeled on the low TDA tier and may include:

- about `+5%` effective economic income or an equivalent expense reduction;
- up to `-10%` supply consumption during the civil war;
- about `+5%` military-factory output;
- bounded defensive assistance during serious retreat.

AI receives the same inflation, debt, crisis, and default rules as the player. The assistance does not create free cash or a separate debt capacity. It does not grant free technologies, attack multipliers, unlimited equipment, or inflation immunity. Conditional assistance is removed when its condition ends.

### 14.4 Performance

- Weekly accounting consumes cached scalar policy and law values.
- `has_idea` wrappers and full building recounts must not be reachable through the weekly call graph.
- Full building recount runs only on initialization, migration, scheduled full refresh, and relevant dirty ownership/building events.
- Policy changes refresh only their dependent expenses, modifiers, forecast, and UI.
- Automatic borrowing must not rebuild all spending ideas every week.

## 15. Economy UI and tooltips

The main panel is compact but actionable:

- the whole policy row has a useful hover area;
- level controls and arrows have larger hitboxes;
- current level and short effect are visible;
- tooltip preview shows the next level, weekly cost delta, effects, and cooldown;
- disabled controls state the exact reason;
- diagnostic slogans such as "money is calculated automatically" are removed from the main view.

Short tooltips answer what a value means and whether it is currently healthy. Delayed tooltips explain the calculation and available responses.

Separate tooltips cover:

- **inflation:** current value, weekly change, sources, expense multiplier, gameplay effects, thresholds, and reduction methods;
- **debt:** principal, weekly interest, interest share of income, current pressure tier, automatic borrowing, and default risk;
- **treasury and balance:** current cash, source breakdown, expense categories, weekly balance, recommended reserve, and deficit runway;
- **policies:** current effect and cost, next-level delta, cooldown, and disabled reason.

Automatic-loan behavior belongs in the debt tooltip and its notification, not as a permanent banner.

## 16. Repository inventory and structure

Repository cleanup is responsibility-driven.

### 16.1 Tools layout

- `tools/builders/`
- `tools/validators/`
- `tools/tests/`
- `tools/lib/`
- `tools/data/`
- `tools/assets/reference/`
- `third_party/hoi4_flag_maker/`

Old root commands remain temporarily available through small compatibility facades. Internal imports move to the structured paths before facades are retired.

Add:

- root `.gitignore`;
- root `AGENTS.md` for future Codex agents;
- tool/test documentation;
- a generated-output ownership registry;
- explicit `--check` and `--apply` modes for mutating builders;
- one documented full static-gate command.

Tracked `__pycache__`, `.pyc`, console history, and other verified transient artifacts are removed. Candidate archives, disabled files, or empty engine files are deleted only after proving they are not required or user-owned source material.

### 16.2 File consolidation

Country-tag definitions may be grouped by region. Related events, decisions, focuses, AI strategies, and shared helpers may be grouped by subsystem. State history, map data, strategic regions, generated technology output, and engine-sensitive OOB files are not merged merely to reduce file count.

## 17. Internationalisation boundary

- All technical IDs, template names, `create_unit` strings, generator symbols, and internal references use ASCII/English.
- New and substantially rewritten player-facing content receives Russian and English localisation.
- Existing untranslated legacy keys are inventoried as debt and are not machine-translated as part of this project.
- Conflicting duplicate localisation keys are resolved.
- Russian localisation remains UTF-8 BOM.

## 18. Save migration and error handling

Migrations are versioned and idempotent. They cover:

- WRK tag-semantic transition and temporary claimants;
- phase reconstruction;
- dirty-zone stage reconstruction;
- regional outcome flags;
- economy schema and obsolete policies;
- renamed templates and repaired ideas.

Event IDs are centrally inventoried. A retry has a fixed maximum, explicit terminal state, and diagnostic log. No effect may mark success before war declaration, ownership transfer, tag formation, or idea migration has actually succeeded.

## 19. Verification and acceptance

### 19.1 Static gates

For each subsystem:

1. add a failing behavioral contract;
2. implement the smallest change that satisfies it;
3. run focused tests and validators;
4. run the complete unit suite;
5. run `python -B tools/validate_tc.py --limit 300`;
6. run `git diff --check`;
7. validate BOM, event IDs, localisation uniqueness, generated ownership, template references, and prohibited polling.

Static success is reported as static success only.

### 19.2 Runtime and visual gates

After map, defines, AI, technology, ideas, GFX, localisation rename, or GUI changes, fully restart HOI4.

Required evidence includes:

- fresh `error.log`, `game.log`, and `system.log`;
- new-campaign startup and an old-save migration smoke test;
- economy panel and tooltip inspection at practical resolutions;
- active aircraft missions in reachable regions;
- correct claimant formation, regional wars, postwar WRK route, and coring;
- dirty-zone progression through all three January 2163 events;
- 8-12 observer campaigns recording war start/end, winner, longest period without meaningful movement, northern progress, aircraft use, and emergency mobilizations;
- targeted saves for each central route and key regional-outcome class.

The release gate does not pass if the campaign evidence still shows deterministic WRK victory, multi-year northern inactivity, unused aircraft, silent launch failure, broken UI hitboxes, or runaway militia spawning.

## 20. Implementation and commit sequence

1. design specification;
2. frozen-tree inventory and repository/tooling foundation;
3. technical ASCII/OOB migration;
4. economy schema, logic, AI, UI, and tooltips;
5. civil-war tag semantics and phase controller;
6. claimant focus/decision skeletons and regional-outcome matrix;
7. map, population, VP, supply, templates, and OOB balance;
8. military AI, air use, militia, and anti-stall behavior;
9. coring, postwar WRK, and progressive dirty-zone opening;
10. integration fixes and runtime acceptance.

Each commit is thematic, reviewable, and independently checked. Before every commit, inspect the staged file list and staged diff. The final audit includes the complete user-approved working set so no existing user work is silently lost or omitted. Push remains out of scope unless requested separately.
