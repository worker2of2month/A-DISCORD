# NAM Total Partition and EFL-AZH Alliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make EFL and AZH fight NAM in one permanent faction and guarantee that neither NAM nor the temporary SLF uprising survives a coalition settlement.

**Architecture:** Keep the existing NAM scenario boundary and replace only its war topology and scripted resolutions. EFL creates the faction and declares the war, AZH joins that same war with `add_to_war`, and the existing capitulation router funnels every defeat of NAM into one deterministic partition effect; focused static contracts lock the ordering, recipients, annexation cleanup, localisation, and removal of the obsolete republic route.

**Tech Stack:** Hearts of Iron IV Clausewitz script, Python 3 focused validator, Russian YAML localisation with UTF-8 BOM, PowerShell verification commands.

## Global Constraints

- Follow `docs/superpowers/specs/2026-08-04-nam-total-partition-and-alliance-design.md` exactly.
- EFL is the permanent faction leader; AZH is a member before either country fights NAM.
- EFL and AZH must participate in one war, not two independent wars against NAM.
- SLF may exist only as the temporary state-688 wartime uprising and must not survive any settlement.
- Coalition allocation is exact: EFL receives `67, 225, 228, 230, 231, 688`; AZH receives `226, 227, 229, 689`.
- A surviving unexpected NAM state is annexed into EFL as a safety net.
- A NAM victory also annexes SLF and restores state 688 to NAM.
- The EFL-AZH faction remains after coalition victory, NAM victory, and timeout resolution.
- Preserve mobilisation, OOBs, equipment, AI strategies, the 420-day timeout, fleets, country history, map generation, and economy content.
- Preserve UTF-8 BOM in `localisation/russian/ADISCORD_nam_resource_war_l_russian.yml`.
- The implementation files below are pre-existing untracked work. Do not stage or commit them from this plan because doing so would capture their entire unrelated baseline; keep the implementation unstaged and report the final scoped status.
- Static validation cannot prove runtime faction membership or final map geometry; require a fresh in-game scenario for those claims.

## File Map

- `tools/validate_adiscord_nam_resource_war.py`: owns focused static contracts and the red-green regression signal.
- `common/scripted_effects/ADISCORD_nam_resource_war_effects.txt`: owns faction creation, shared-war entry, territorial settlement, and country cleanup.
- `common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt`: routes NAM capitulation by EFL, AZH, or SLF to the same coalition effect.
- `common/decisions/ADISCORD_scenario_debug_decisions.txt`: exposes only production outcomes that remain valid.
- `events/ADISCORD_nam_resource_war_events.txt`: contains the war-start news and two surviving outcome news events.
- `localisation/russian/ADISCORD_nam_resource_war_l_russian.yml`: supplies the faction name and revised public/debug text while retaining BOM.
- `docs/testing/vorkerland_and_nam_debug.md`: records the new debug procedure and expected final tags/states.

---

### Task 1: Permanent faction and one shared war

**Files:**
- Modify: `tools/validate_adiscord_nam_resource_war.py:197-213,482-519`
- Modify: `common/scripted_effects/ADISCORD_nam_resource_war_effects.txt:26-61`
- Modify: `localisation/russian/ADISCORD_nam_resource_war_l_russian.yml:20-29`

**Interfaces:**
- Consumes: `named_block(source, name)`, `check(condition, message)`, `faction_template_ADISCORD_standard`, and the existing EFL/AZH mobilisation blocks.
- Produces: faction key `faction_eflor_azhar_restitution_alliance`, an EFL-led faction containing AZH, and one EFL-versus-NAM war joined by AZH through `add_to_war`.

- [ ] **Step 1: Establish the focused green baseline**

Run:

```powershell
python -B tools/validate_adiscord_nam_resource_war.py
```

Expected: exit `0` with `NAM resource-war validation passed.` before the new contract is added.

- [ ] **Step 2: Replace the two-declaration contract with a faction-and-shared-war contract**

In `tools/validate_adiscord_nam_resource_war.py`, replace the checks that require declarations from both EFL and AZH with:

```python
    start = named_block(effects, "ADISCORD_nam_resource_war_start")
    faction_creation = re.compile(
        r"create_faction_from_template\s*=\s*\{\s*"
        r"template\s*=\s*faction_template_ADISCORD_standard\s+"
        r"name\s*=\s*faction_eflor_azhar_restitution_alliance\s*\}",
        re.DOTALL,
    )
    check(faction_creation.search(start) is not None,
          "resource-war start does not create the permanent EFL-AZH faction")
    check(start.count("add_to_faction = AZH") == 1,
          "EFL must add AZH to the resource-war faction exactly once")
    check(start.count("leave_faction = yes") == 3,
          "NAM, EFL, and AZH must clear obsolete faction ties before the new faction is formed")

    efl_declaration = "EFL = { declare_war_on = { target = NAM type = annex_everything } }"
    azh_join_pattern = re.compile(
        r"AZH\s*=\s*\{\s*add_to_war\s*=\s*\{\s*"
        r"targeted_alliance\s*=\s*EFL\s+enemy\s*=\s*NAM\s+"
        r"hostility_reason\s*=\s*asked_to_join\s+single_target_only\s*=\s*yes\s*\}\s*\}",
        re.DOTALL,
    )
    check(efl_declaration in start, "EFL does not declare the NAM annexation war")
    check(azh_join_pattern.search(start) is not None,
          "AZH does not join EFL's existing war against NAM")
    check("AZH = { declare_war_on = { target = NAM" not in start,
          "AZH still creates an independent second war against NAM")

    create_position = start.find("create_faction_from_template")
    declare_position = start.find(efl_declaration)
    join_position = start.find("add_to_war")
    check(-1 not in (create_position, declare_position, join_position)
          and create_position < declare_position < join_position,
          "faction creation, EFL declaration, and AZH war entry are in the wrong order")
```

After `loc` is decoded, add:

```python
    check('faction_eflor_azhar_restitution_alliance: "Эфлорско-ажарский союз"' in loc,
          "missing Russian localisation for the permanent EFL-AZH faction")
```

- [ ] **Step 3: Run the focused validator and observe the intended failure**

Run:

```powershell
python -B tools/validate_adiscord_nam_resource_war.py
```

Expected: exit `1` with failures for missing faction creation, missing AZH `add_to_war`, the remaining independent AZH declaration, wrong action ordering, and missing faction localisation.

- [ ] **Step 4: Create the faction before hostilities and join AZH to EFL's war**

In `ADISCORD_nam_resource_war_start`, replace the claim/declaration tail with this exact sequence after both mobilisation blocks have made EFL and AZH leave obsolete factions:

```hoi4
        EFL = {
            create_faction_from_template = {
                template = faction_template_ADISCORD_standard
                name = faction_eflor_azhar_restitution_alliance
            }
            add_to_faction = AZH
        }

        67 = { add_claim_by = EFL add_claim_by = AZH }
        EFL = { declare_war_on = { target = NAM type = annex_everything } }
        AZH = {
            add_to_war = {
                targeted_alliance = EFL
                enemy = NAM
                hostility_reason = asked_to_join
                single_target_only = yes
            }
        }
```

Do not add a faction teardown to any resolution effect.

- [ ] **Step 5: Add the faction name and make the coalition spirit consistent with permanence**

Add directly below `l_russian:` while preserving the existing BOM:

```yaml
 faction_eflor_azhar_restitution_alliance: "Эфлорско-ажарский союз"
```

Replace `ADISCORD_nam_restitution_coalition_desc` with:

```yaml
 ADISCORD_nam_restitution_coalition_desc: "Эфлор и Ажар оформили постоянный военно-политический союз ради возвращения территорий и ресурсной инфраструктуры, отторгнутых Воркерландом и унаследованных Светлогорьем. Совместный штаб координирует одну войну и останется основой их безопасности после неё."
```

- [ ] **Step 6: Verify the first red-green cycle**

Run:

```powershell
python -B tools/validate_adiscord_nam_resource_war.py
```

Expected: exit `0` with `NAM resource-war validation passed.`

- [ ] **Step 7: Inspect only the Task 1 files and leave them unstaged**

Run:

```powershell
git status --short -- tools/validate_adiscord_nam_resource_war.py common/scripted_effects/ADISCORD_nam_resource_war_effects.txt localisation/russian/ADISCORD_nam_resource_war_l_russian.yml
```

Expected: the three pre-existing feature files remain `??`; do not run `git add` for them.

---

### Task 2: Deterministic total partition and removal of the republic outcome

**Files:**
- Modify: `tools/validate_adiscord_nam_resource_war.py:182-186,233-353,482-529`
- Modify: `common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt:21-67`
- Modify: `common/scripted_effects/ADISCORD_nam_resource_war_effects.txt:105-217,268-285`
- Modify: `common/decisions/ADISCORD_scenario_debug_decisions.txt:95-125`
- Modify: `events/ADISCORD_nam_resource_war_events.txt:47-90`
- Modify: `localisation/russian/ADISCORD_nam_resource_war_l_russian.yml:35-55`
- Modify: `docs/testing/vorkerland_and_nam_debug.md:8,19-21`

**Interfaces:**
- Consumes: `ADISCORD_nam_resource_war_end_all_wars`, `ADISCORD_nam_resource_war_clear_temporary_support`, the Task 1 faction, and `named_block` validator parsing.
- Produces: one `ADISCORD_nam_resource_war_resolve_coalition_victory` route for defeat of NAM by EFL/AZH/SLF, exact recipient state sets, NAM/SLF cleanup annexations, and only three NAM news/debug outcomes.

- [ ] **Step 1: Replace the obsolete uprising-success contracts with total-partition contracts**

In the validator, require exactly three news events and replace the event/outcome lists with:

```python
    check(news.count("news_event = {") == 3,
          "world news must contain exactly war start and two mutually exclusive outcomes")

    news_blocks = typed_blocks(news, "news_event")
    for event_id in (
        "ADISCORD_nam_resource_news.1",
        "ADISCORD_nam_resource_news.2",
        "ADISCORD_nam_resource_news.3",
    ):
        definitions = [block for block in news_blocks if re.search(
            rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", block
        )]
        check(len(definitions) == 1, f"{event_id} must have exactly one definition")
        if definitions:
            check("is_triggered_only = yes" in definitions[0]
                  and "fire_only_once = yes" in definitions[0],
                  f"{event_id} must be triggered-only and single-shot")

    expected_news_calls = {
        "ADISCORD_nam_resource_news.1": "ADISCORD_nam_resource_war_start",
        "ADISCORD_nam_resource_news.2": "ADISCORD_nam_resource_war_resolve_coalition_victory",
        "ADISCORD_nam_resource_news.3": "ADISCORD_nam_resource_war_resolve_nam_victory",
    }

    for effect_name in (
        "ADISCORD_nam_resource_war_resolve_coalition_victory",
        "ADISCORD_nam_resource_war_resolve_nam_victory",
    ):
        outcome = named_block(effects, effect_name)
        check("ADISCORD_nam_resource_war_active = yes" in outcome
              and "set_global_flag = ADISCORD_nam_resource_war_resolved" in outcome,
              f"{effect_name} lacks the active-war/single-resolution guard")
```

Remove the checks that require the uprising-victory effect, debug decision, `.4` news, republic cosmetic transition, NAM state-689 remnant, and SLF-only capitulation branch. Add these exact contracts after extracting the terminal blocks:

```python
    obsolete_uprising_tokens = (
        "ADISCORD_nam_resource_war_resolve_uprising_victory",
        "ADISCORD_nam_debug_resolve_uprising_victory",
        "ADISCORD_nam_resource_news.4",
        "set_cosmetic_tag = SLF_svetlogorsk_republic",
        "SLF_svetlogorsk_republic_proclaimed",
    )
    terminal_sources = "\n".join((effects, on_actions, debug_decisions, news))
    for token in obsolete_uprising_tokens:
        check(token not in terminal_sources,
              f"obsolete surviving-SLF route remains: {token}")

    capitulation = named_block(on_actions, "on_capitulation")
    coalition_route = re.search(
        r"ROOT\s*=\s*\{\s*tag\s*=\s*NAM\s*\}.*?"
        r"FROM\s*=\s*\{\s*OR\s*=\s*\{([^}]*)\}.*?"
        r"ADISCORD_nam_resource_war_resolve_coalition_victory\s*=\s*yes",
        capitulation,
        re.DOTALL,
    )
    check(coalition_route is not None
          and all(f"tag = {tag}" in coalition_route.group(1) for tag in ("EFL", "AZH", "SLF")),
          "NAM defeat by EFL, AZH, or SLF must use the coalition settlement")

    coalition_victory = named_block(
        effects, "ADISCORD_nam_resource_war_resolve_coalition_victory"
    )
    efl_settlement = named_block(coalition_victory, "EFL")
    azh_settlement = named_block(coalition_victory, "AZH")
    efl_states = set(re.findall(r"transfer_state\s*=\s*(\d+)", efl_settlement))
    azh_states = set(re.findall(r"transfer_state\s*=\s*(\d+)", azh_settlement))
    check(efl_states == {"67", "225", "228", "230", "231", "688"},
          f"EFL coalition allocation is wrong: {sorted(efl_states)}")
    check(azh_states == {"226", "227", "229", "689"},
          f"AZH coalition allocation is wrong: {sorted(azh_states)}")
    check("annex_country = { target = SLF transfer_troops = no }" in efl_settlement,
          "EFL does not eliminate the temporary SLF uprising")
    check("annex_country = { target = NAM transfer_troops = no }" in coalition_victory,
          "coalition settlement lacks the NAM residual-state safety annexation")
    check("688 = { remove_core_of = SLF remove_core_of = NAM add_core_of = EFL set_state_controller_to = EFL }"
          in coalition_victory, "state 688 cleanup is incomplete")
    check("689 = { remove_core_of = NAM add_core_of = AZH set_state_controller_to = AZH }"
          in coalition_victory, "state 689 cleanup is incomplete")

    nam_victory = named_block(effects, "ADISCORD_nam_resource_war_resolve_nam_victory")
    check("annex_country = { target = SLF transfer_troops = no }" in nam_victory,
          "NAM victory does not eliminate a surviving SLF uprising")
    check("transfer_state = 688" in nam_victory
          and "688 = { remove_core_of = SLF add_core_of = NAM set_state_controller_to = NAM }" in nam_victory,
          "NAM victory does not restore state 688 and remove its temporary SLF core")

    for outcome in (coalition_victory, nam_victory):
        check(all(token not in outcome for token in (
            "leave_faction = yes", "remove_from_faction", "dismantle_faction"
        )), "NAM resolution must not dismantle the permanent EFL-AZH faction")
```

Replace the localisation-key tuple and debug-prefix check with:

```python
    for key in (
        "SLF_Yaroslav_Veter",
        "ADISCORD_coastal_patrol_vessel",
        "ADISCORD_coastal_patrol_ship",
        "ADISCORD_coastal_patrol_ship_1",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_training_factor",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_mission_factor",
        "modifier_experience_gain_ADISCORD_coastal_patrol_vessel_combat_factor",
        "ADISCORD_nam_resource_news.1.t",
        "ADISCORD_nam_resource_news.1.d",
        "ADISCORD_nam_resource_news.1.a",
        "ADISCORD_nam_resource_news.2.t",
        "ADISCORD_nam_resource_news.2.d",
        "ADISCORD_nam_resource_news.2.a",
        "ADISCORD_nam_resource_news.3.t",
        "ADISCORD_nam_resource_news.3.d",
        "ADISCORD_nam_resource_news.3.a",
        "ADISCORD_nam_debug_start_resource_war",
        "ADISCORD_nam_debug_resolve_coalition_victory",
        "ADISCORD_nam_debug_resolve_nam_victory",
    ):
        check(re.search(rf"(?m)^\s*{re.escape(key)}:", loc) is not None,
              f"missing localisation key {key}")
    check("ADISCORD_nam_resource_news.4" not in loc,
          "obsolete uprising-victory news localisation remains")
    check("ADISCORD_nam_debug_resolve_uprising_victory" not in loc,
          "obsolete uprising-victory debug localisation remains")
    check(loc.count("§RDEBUG:§!") == 3,
          "all three debug entry points need the red DEBUG prefix")
```

- [ ] **Step 2: Run the focused validator and observe the intended settlement failures**

Run:

```powershell
python -B tools/validate_adiscord_nam_resource_war.py
```

Expected: exit `1`; failures identify the surviving-SLF route, the missing `688`/`689` recipient assignments, missing SLF/NAM annexation cleanup, missing NAM-victory cleanup, and the obsolete fourth news/debug outcome.

- [ ] **Step 3: Route every defeat of NAM to the coalition settlement**

Replace the first two NAM-defeat branches in `on_capitulation` with one branch:

```hoi4
            if = {
                limit = {
                    ADISCORD_nam_resource_war_active = yes
                    ROOT = { tag = NAM }
                    FROM = { OR = { tag = EFL tag = AZH tag = SLF } }
                }
                set_global_flag = skip_default_capitulation
                NAM = { ADISCORD_nam_resource_war_resolve_coalition_victory = yes }
            }
```

Keep the later EFL, AZH, and SLF defeat-recording branches unchanged.

- [ ] **Step 4: Replace the coalition settlement with exact partition and cleanup scopes**

Keep the existing resolution flags and `ADISCORD_nam_resource_war_end_all_wars = yes`, then replace the territorial portion of `ADISCORD_nam_resource_war_resolve_coalition_victory` with:

```hoi4
        EFL = {
            if = {
                limit = { SLF = { exists = yes } }
                annex_country = { target = SLF transfer_troops = no }
            }
            transfer_state = 67
            transfer_state = 225
            transfer_state = 228
            transfer_state = 230
            transfer_state = 231
            transfer_state = 688
        }
        67 = { add_core_of = EFL set_state_controller_to = EFL }
        225 = { add_core_of = EFL set_state_controller_to = EFL }
        228 = { add_core_of = EFL set_state_controller_to = EFL }
        230 = { add_core_of = EFL set_state_controller_to = EFL }
        231 = { add_core_of = EFL set_state_controller_to = EFL }
        688 = { remove_core_of = SLF remove_core_of = NAM add_core_of = EFL set_state_controller_to = EFL }

        AZH = {
            transfer_state = 226
            transfer_state = 227
            transfer_state = 229
            transfer_state = 689
        }
        226 = { add_core_of = AZH set_state_controller_to = AZH }
        227 = { add_core_of = AZH set_state_controller_to = AZH }
        229 = { add_core_of = AZH set_state_controller_to = AZH }
        689 = { remove_core_of = NAM add_core_of = AZH set_state_controller_to = AZH }

        if = {
            limit = { NAM = { exists = yes } }
            EFL = { annex_country = { target = NAM transfer_troops = no } }
        }
```

Retain temporary-support cleanup and call news `.2` from EFL after the annexation safety net.

- [ ] **Step 5: Eliminate SLF in the NAM-victory effect**

Immediately after `ADISCORD_nam_resource_war_end_all_wars = yes`, add:

```hoi4
        NAM = {
            if = {
                limit = { SLF = { exists = yes } }
                annex_country = { target = SLF transfer_troops = no }
            }
            transfer_state = 688
        }
        688 = { remove_core_of = SLF add_core_of = NAM set_state_controller_to = NAM }
```

Keep the existing state-68 transfer, state-69 claim, stability, temporary-support cleanup, and news `.3` call.

- [ ] **Step 6: Remove every callable republic outcome**

Delete these complete definitions:

```text
ADISCORD_nam_resource_war_resolve_uprising_victory
ADISCORD_nam_debug_resolve_uprising_victory
ADISCORD_nam_resource_news.4
ADISCORD_nam_debug_resolve_uprising_victory decision
```

Do not delete the temporary SLF tag, state-688 uprising start effect, OOB, leader, flag, or wartime event.

- [ ] **Step 7: Update Russian text and the manual debug contract**

Preserve the localisation BOM and make these replacements:

```yaml
 ADISCORD_nam_resource_news.2.d: "Оборона NAM рухнула. Эфлор занял Северные месторождения, западные терминалы и Светлогорск, а Ажар — обслуживающие Чёрный бассейн морские округа и южный порт. Временный штаб восстания был распущен, остатки администрации NAM ликвидированы. Эфлорско-ажарский союз объявил цель войны достигнутой и приступил к демаркации общей границы."
 ADISCORD_nam_resource_news.3.d: "Армия NAM удержала Северные месторождения и вынудила Эфлор с Ажаром подписать хартию признания. Светлогорье получает узкий эфлорский приграничный округ и формальную претензию на Чёрный бассейн, но отказывается от дальнейшего наступления. Светлогорское восстание разоружено и ликвидировано, а союз двух соседей сохраняется после перемирия."
 ADISCORD_nam_debug_start_resource_war_desc: "Освобождает NAM от старых союзных связей, создаёт постоянный Эфлорско-ажарский союз и запускает его общую войну против Светлогорья."
 ADISCORD_nam_debug_resolve_coalition_victory_desc: "Полностью разделяет NAM между Эфлором и Ажаром, ликвидирует Светлогорское восстание и сохраняет союз победителей."
 ADISCORD_nam_debug_resolve_nam_victory_desc: "Завершает войну признанием Светлогорья, ограниченной передачей приграничного штата и ликвидацией уцелевшей повстанческой армии; союз соседей сохраняется."
```

Remove the `.4` news keys and uprising-victory debug keys from the same file.

In `docs/testing/vorkerland_and_nam_debug.md`, state these exact expectations:

```markdown
- За `NAM`, `EFL`, `AZH` или `SLF`: запустите ресурсную войну, затем при необходимости принудительно примените победу соседей или победу NAM.
- При победе соседей EFL получает `67`, `225`, `228`, `230`, `231`, `688`; AZH получает `226`, `227`, `229`, `689`; NAM и SLF больше не существуют, а EFL и AZH остаются в одном альянсе.
- При победе NAM восстание SLF ликвидируется, штат `688` возвращается NAM, а EFL и AZH сохраняют общий альянс.
```

- [ ] **Step 8: Verify the second red-green cycle**

Run:

```powershell
python -B tools/validate_adiscord_nam_resource_war.py
python -B -m unittest tools.test_vorkerland_nam_state_balance -q
```

Expected: focused validator exit `0`; related unit tests report all tests passing.

- [ ] **Step 9: Inspect the complete implementation subset and leave it unstaged**

Run:

```powershell
git status --short -- tools/validate_adiscord_nam_resource_war.py common/scripted_effects/ADISCORD_nam_resource_war_effects.txt common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt common/decisions/ADISCORD_scenario_debug_decisions.txt events/ADISCORD_nam_resource_war_events.txt localisation/russian/ADISCORD_nam_resource_war_l_russian.yml docs/testing/vorkerland_and_nam_debug.md
```

Expected: only the seven pre-existing untracked scenario files are listed as `??`; do not stage them.

---

### Task 3: Full static verification and runtime handoff

**Files:**
- Verify: `tools/validate_adiscord_nam_resource_war.py`
- Verify: `tools/test_vorkerland_nam_state_balance.py`
- Verify: `tools/validate_tc.py`
- Inspect: the seven implementation files listed in Task 2

**Interfaces:**
- Consumes: the completed Task 1 and Task 2 script/localisation changes.
- Produces: fresh focused and project-level evidence plus a precise in-game scenario checklist; no new files or staging.

- [ ] **Step 1: Run the focused contract from a fresh process**

```powershell
python -B tools/validate_adiscord_nam_resource_war.py
```

Expected: exit `0` and `NAM resource-war validation passed.`

- [ ] **Step 2: Run the related state-balance suite from a fresh process**

```powershell
python -B -m unittest tools.test_vorkerland_nam_state_balance -q
```

Expected: exit `0` with no failures or errors.

- [ ] **Step 3: Run the project validator**

```powershell
python -B tools/validate_tc.py --limit 300
```

Expected: exit `0`, or report pre-existing findings separately only when the output names files outside the seven-file implementation subset.

- [ ] **Step 4: Check whitespace for tracked and untracked implementation files**

Run the tracked check:

```powershell
git diff --check
```

Then run this untracked-file check:

```powershell
$namFiles = @(
    'tools/validate_adiscord_nam_resource_war.py',
    'common/scripted_effects/ADISCORD_nam_resource_war_effects.txt',
    'common/on_actions/03_ADISCORD_nam_resource_war_on_actions.txt',
    'common/decisions/ADISCORD_scenario_debug_decisions.txt',
    'events/ADISCORD_nam_resource_war_events.txt',
    'localisation/russian/ADISCORD_nam_resource_war_l_russian.yml',
    'docs/testing/vorkerland_and_nam_debug.md'
)
$namWhitespaceIssues = @()
foreach ($namFile in $namFiles) {
    $namCheck = git diff --no-index --check -- NUL $namFile 2>&1
    if ($namCheck -match 'trailing whitespace|space before tab|new blank line') {
        $namWhitespaceIssues += $namCheck
    }
}
if ($namWhitespaceIssues.Count -gt 0) {
    $namWhitespaceIssues
    exit 1
}
```

Expected: no whitespace-error output. Existing unrelated tracked findings, if any, are reported with their paths and are not edited.

- [ ] **Step 5: Re-read the requirement matrix against current source**

Confirm all of these from the final files:

```text
Faction created before war: faction_eflor_azhar_restitution_alliance
Faction leader/member: EFL/AZH
War topology: EFL declare_war_on; AZH add_to_war
Coalition EFL states: 67 225 228 230 231 688
Coalition AZH states: 226 227 229 689
Coalition survivors: EFL and AZH only; NAM and SLF absent
NAM victory SLF cleanup: NAM annex_country SLF and transfer_state 688
Post-war faction teardown tokens: absent
News outcomes: .1 start, .2 coalition, .3 NAM
Russian localisation BOM: present
```

- [ ] **Step 6: Hand off the runtime verification without claiming it was performed**

Use the existing debug category in a fresh campaign:

```text
1. Start the NAM resource war as NAM, EFL, AZH, or SLF.
2. Confirm EFL leads faction_eflor_azhar_restitution_alliance and AZH is a member.
3. Confirm both neighbours are in the same war against NAM.
4. Trigger the coalition-victory debug action.
5. Confirm EFL owns 67, 225, 228, 230, 231, 688.
6. Confirm AZH owns 226, 227, 229, 689.
7. Confirm NAM and SLF do not exist and EFL/AZH remain allied.
8. In a second fresh campaign, trigger NAM victory and confirm SLF is removed, NAM owns 688, and EFL/AZH remain allied.
```

Report static evidence separately from this required runtime check. Do not claim visual or runtime success without a fresh screenshot/log from the new campaign.
