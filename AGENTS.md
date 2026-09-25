# A-Discord repository rules

## Generated output

Treat the generator that names an output in its header or source as the owner
of that output. Update the generator and regenerate; do not hand-edit generated
state history, strategic regions, technology data, map buildings, or generated
localisation to make a one-off correction. Use the builder's dry-run or
`--check` mode before its explicit `--apply` mode, then prove a second run is
idempotent when the builder changes data.

## Public release

Debug decisions and their required events, categories, and localisation may be
included in the public release. Do not exclude them solely because they are debug content.

## Localisation encoding

Russian localisation files use UTF-8 with a BOM. Preserve that BOM and verify
it after editing; do not use shell rewrites that can remove it or corrupt
Cyrillic text. Gameplay `.txt` scripts use UTF-8 without a BOM; a BOM in a
decision file can make the engine reject the first definition. Do not apply the
localisation encoding rule to gameplay scripts.
Keep each localisation value on one physical line; encode paragraph breaks as
literal `\n\n`. Checking that a key exists does not prove its quoted value loads.

Никогда не добавляй локализацию "зоне отчуждения".

## File organisation

Group related country content in one file per engine data type, using clear
sections inside it. Do not create another file for each focus, district,
crisis stage, reward, or agent's subtask. Extend the existing country file;
split only when the engine format or a separately owned shared system needs
it. File length alone is not a reason to fragment a coherent mechanic.
For STP, scripted effects belong in `ADISCORD_STP_scripted_effects.txt` and
scripted triggers in `ADISCORD_STP_scripted_triggers.txt`, including the regional
and civil-war conditions. Do not put country-specific triggers in generic files.
STP events belong in `events/ADISCORD_STP_events.txt`; decisions and their
categories belong in `ADISCORD_STP_decisions.txt` and
`ADISCORD_decision_categories_STP.txt`. Preparation, war, and intervention are
sections of those files, not separate files.
Russian STP localisation belongs in `localisation/russian/ADISCORD_STP_l_russian.yml`;
focuses, decisions, BOP, interface and war text are sections of that file.
STP scripted localisation belongs in `common/scripted_localisation/ADISCORD_STP_scripted_loc.txt`,
including district status and preparation summaries.
Country lifecycle on_actions belong in `common/on_actions/02_ADISCORD_STP_on_actions.txt`.
Scripted peace and capitulation dispatch is shared in
`common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt`, with ordered
country sections inside each native hook. Do not duplicate those hooks in
country files. Keep effects, triggers and treaty-choice events in their existing
country files. Northern reservation follows the settlement handlers; Livonn
completion follows the SRP military result. The separate
`ZZ_ADISCORD_default_capitulation_on_actions.txt` remains last.
Update explicit tooling source views and verify the full native callback order
when moving a handler. The shared startup
initializer retains its single STP entry call before economy initialization.
When consolidating, preserve script IDs and scope, update tools and docs that
read the old paths, and remove the superseded files after verifying all
definitions were retained exactly once.

## Code comments

Комментарии объясняют нетривиальное поведение, область действия, порядок вызовов
и ограничения движка. Не пересказывай очевидный код.
Не пиши в комментариях, что код взят из TFR или другого мода, сделан «по примеру»
чужой реализации либо перенесён агентом. Не ссылайся на конкретные сохранения,
скриншоты, временные каталоги, переписку, оценки агентов и историю прогонов.
Не оставляй отчёты «раньше было / теперь исправлено», похвалу решению и другие
следы рабочего процесса. Оставляй только информацию, нужную для сопровождения
текущего кода; техническую документацию также не превращай в дневник работы.

## Code style

Keep authored Clausewitz blocks consistently tab-indented. Use one statement per
line when a block contains several conditions or effects; compact one-line
blocks are for genuinely atomic clauses, not whole decision or focus bodies.
Keep related top-level definitions separated by one blank line.

Python source uses ordinary one-statement-per-line formatting. Do not join
statements with `;`; temporary investigation scripts such as `_tmp_*.py`
must stay untracked. Prefer small named helpers over dense nested expressions
when the same condition or transformation is repeated.

Style-only cleanup must not change gameplay semantics. Do not bulk-format
vanilla-derived interface files or generated outputs merely to make whitespace
uniform. Fix authored sections and their generators instead.

## Gameplay rewards and UI

Joining alliances, creating factions, and declaring wars are disabled diplomatic
actions in this mod. Players may do these only through scripted focuses,
decisions, and their events. Do not re-enable these actions in a focus reward
or a postwar cleanup. Design war entry, allies, and peace outcomes around the
scripted routes; ordinary diplomatic UI is not an available fallback.
Use the existing NCNS faction template for scripted alliance creation. A coalition war must add allies to the intended side of the same war. If every member must be defeated, give mandatory-major status only for that campaign and clear it on every terminal path; a liberated member must block a final settlement again.

Prefer native effect output and `unlock_decision_tooltip` for rewards and
decision unlocks. In national focuses, an ordinary decision unlock stays compact:
use `unlock_decision_tooltip = <id>` and keep the decision's price, duration,
conditions and full effect inside the decision. Do not inline `show_effect_tooltip = yes`
or duplicate `<decision>_desc` there; add at most one short contextual tooltip only
when the unlock name is insufficient. Combine rewards when they support the same player action:
persistent capability, immediate result, and a paid follow-up are useful
partners; arbitrary bonus padding is not. Reserve custom tooltips for unique
mechanics, delayed results, and recipient or cost conditions that native output
cannot explain.
Check the whole focus route: a promised unlock must be usable at that point,
an exclusive branch must give a meaningful alternative, and a delayed reward
must reach the country the player will control. Do not gate a shared story
effect behind one side's focus; audit every caller when changing its conditions.
For an announced threat, add the prerequisite focus time and the response's
own duration before choosing its first deadline. Forced focus completion in a
QA fixture must not conceal an impossible first response in a normal campaign.
A promised period of preparation must permit its mobilization and production
programs before the attack. Check availability, cancellation and final delivery
against the same current threat; an offer of peace must close that threat cleanly.
Army role policies must follow each participant's own conflict. Ending the
STP-STS war must not send SRP's frontline formations back to garrison duty while
its separate war with VAL continues.
An autonomous country's mobilization belongs to that country and must survive
another country's election, tag change or focus-tree replacement.
Use existing icons that communicate the focus action. Inspect the texture as
well as its sprite name; a descriptive alias may still point to a placeholder.
Country variables are authoritative for dynamic modifiers; dummy ideas show
the exact delta through `effect_tooltip` and are never installed. Verify
transfer to successor countries and cleanup when the mechanic ends.
Guard `remove_dynamic_modifier` with `has_dynamic_modifier`; unused branches and successor countries may never have received the modifier.

STP elections determine the winner's mandate. An ordinary victory still leads
to the large civil war. Exceptional legitimacy, a surviving public military
agreement and functioning district administrations may limit the party revolt
to its remaining strongholds. This is an explicit, difficult route, not a random
peace roll or a reward for crossing the ordinary election threshold. Failed
conditions retain their individual military, territorial and political results.
NOD prepares independently before the election result. The northern war blocks
entry, not readiness; allow seven days to redeploy after that war. Neither a
tag change nor a limited revolt resets the countdown. Defeating the party or
defeating NOD in the north closes the intervention route.
Initialize BOP with explicit `set_power_balance = { id = <id> set_value = <value> }` inside a one-time guard; reopening must preserve accumulated progress.
Hide technical flag writes and redundant conditions; localise meaningful
visible conditions so players never see raw flag IDs. Use ASCII `-` for
numeric signs and existing manpower, equipment, and command-power texticons.
Use yellow values on dark UI only; on white event paper use native dark text.
Ordinary event windows adapt to rendered description height. Do not use
`fixedsize` on `Description` to force a small card: it truncates long text.
The native country-event handler finds `event_picture` in `bottom_Window`;
keep it and its frame below the description with positive coordinates.
Do not assume `maxHeight` caps the entire event or that a declared scrollbar
works: verify short/long descriptions and every answer in the running game.
Keep ordinary COUNTRY descriptions in the native expanding mode without a
`scrollbarType`. A scroll viewport can show only part of the text while the
event handler reserves its full height, leaving a large blank area. Verify the
visible last line and its actual distance to the picture in a fresh screenshot;
adding the same assumed text height to both positions in a test proves nothing.
NEWS and COUNTRY pictures have different native dimensions. Inspect the
actual texture and overlay together; a valid sprite ID alone is insufficient.
Use ASCII list markers in event text; the current paper font renders the bullet character as a question mark.
Check actual event description references, including variants such as `.accepted`;
checking only keys ending in `.d` misses text displayed on the same light paper.
Use `visible` for completed-focus unlocks and immediate local context; keep shortages and occupied preparation slots readable in `available` or `custom_cost_trigger`. Keep transient commission/asset predicates out of daily-cached `target_trigger` for immediate responses. Hide technical bookkeeping without hiding the price, material result, cancellation consequence or current risk; do not nest `hidden_effect` inside an already hidden payload.
Narrative and story event prose is not tooltip clutter. Do not shorten, remove, or skip lore/event descriptions as part of focus or tooltip cleanup unless the task explicitly asks to edit that prose.
For numeric gameplay resources in custom localisation, prefer the native texticon next to the value instead of spelling out the resource name: for example `§G+20§! £political_power_texticon`, not `+20 political power`. Apply the same compact pattern to costs and other well-known resources when an appropriate texticon exists; keep prose references textual when no concrete value is being displayed.
Keep generic procurement in national decisions; map decisions need a local
consequence. Reuse the existing regional map and preparation slots. Prefer an existing completed focus, active decision, character state, or
numeric value to another flag. Do not mirror the same fact in several markers.
Keep transient flags only where a delayed operation or lifecycle needs them,
and clear them at every terminal outcome. Before replacing a focus marker
with `has_completed_focus` inside its own reward, verify the engine evaluation
order so the immediate modifier still updates. A flag or
percentage needs a real consumer: election mandate, territory, paid units,
existing stockpiles, or building damage. Preserve resource accounting across
split, cancellation, and delayed callbacks; previews must name the recipient.
Tie an inspection response to the current mission, and check delayed results
against current ownership and operation availability. A lost local asset may
be rebuilt for its full price; never turn a historical completion flag into
an unexplained permanent lock.
An inspection must account for paid local work still in progress. Country
`has_decision` does not reliably detect targeted decisions, including decisions
with one fixed state. Use the existing state escrow or a state flag covering
payment through completion, cancellation and phase cleanup. STP operations
2/3/29/45/46 share `STP_cw_district_operation_in_progress` in their own target;
operation 53 uses its existing `STP_cw_sabotage_rifles` escrow without another flag.
Verify detection, cancellation, reserve return and slot release as one chain.
Successful cover must preserve its promised assets; the worst failure must
remove their actual military rewards, respecting ratified agreements.
When flag age represents an institution's continuous work, keep its existing
date on repeated rewards. Actual loss and reconstruction restart that age;
show readiness and the required duration in the player interface.
Country creation and player handoff are separate phases. Verify both owner and
controller of every guaranteed starting state after the war declaration. Start
hostilities and temporary war bonuses at the actual side choice; cancel
preparation callbacks once armies have been distributed. Preserve an external
country's existing mobilization deadline through the player handoff.
Test the unattended event timeout as well as an immediate player response.
Prepared formations need first claim on real recruits and equipment; adding
spawn attempts after the base army can leave every preparation reward unpaid.
Fixed-price formations must keep their source template name and composition
stable while orders remain available. A template lock must preserve ordinary
recruitment when intended. Every peace route must settle pending orders before
unlocking templates, and later wars must not reopen orders at the obsolete price.
Scale force counts against template manpower, stocks, supply and replenishment,
not just the number of divisions. A crisis clock must also advance when the
player avoids its introductory focuses.
Keep the preparation army summary in the existing decision category. Label
nominal formation plans before resource allocation and show already paid
formations separately; neither is the current deployed army. Refresh the report
when its source inputs change, not through recurring polling. Do not add a
separate report decision or event.
A decision with `custom_cost_text` replaces the native cost handling: set `cost = 0`,
check every declared currency explicitly, and debit each exactly once in
`complete_effect`. Include all prices and their texticons in the custom cost
line. In compact costs and resource amounts, always render the numeric amount first and the texticon second, for example `§Y75§! £political_power_texticon` and `§Y100000§! £population_texticon`; never put the icon before its number. Provide the native `<key>_blocked` and `<key>_tooltip` localisation
variants as well; an affordable screenshot does not exercise the blocked price.
Verify the before/after balances in the running game.
When targeted projects share one country escrow, its presence must block every
new target until settlement clears it. Use the existing deposit as the gate,
not `has_decision`; a second payment must never overwrite the first project's
receipt. Arsenal construction uses `STP_cw_arsenal_deposit` for this contract.
Hide the call to a hidden dispatcher event inside `hidden_effect`; otherwise
native reward text may announce an event named `0`. Keep the real reward visible.
Use exact affordability boundaries for fractional stocks: `NOT = { has_equipment = { infantry_equipment < 480 } }`, not `> 479` for a price of 480. Manpower can also be fractional: use `NOT = { has_manpower < 6000 }` for a 6000-person formation. Check the same price again at delayed settlement.
A focus following exclusive routes needs those alternatives inside one
`prerequisite` block. Reapplying an already unlocked tier is not a reward;
verify a real delta or action remains on every reachable route.
For transactions with another playable country, obtain its in-game choice
before debiting its resources. Keep payment and delivery together, recheck
both parties, and prevent duplicate settlements. An event left open while a focus completes must not revoke or contradict that focus's route; keep a safe close-only option when the course is already fixed. A busy operation should
delay a required story offer rather than silently discard it.
When an existing offer flag stores a package tier, use disjoint native value
comparisons (`< 2` / `> 1`) instead of assuming `value = 1` means exact equality.
The buyer may accept the donor's quoted package, not silently upgrade it.
After changing an economic modifier, invalidate the existing economy cache
with `ADISCORD_economy_mark_dirty`; updating the visible spirit alone does not
refresh the weekly budget.
Long event descriptions must fit the engine text buffer after UTF-8 encoding,
not only the GUI height. Preserve the author's text through bounded pages in
the existing event file when necessary; a scrollbar cannot repair byte truncation.
For long Russian descriptions, use an editorial ceiling of 3000 characters AND
5500 UTF-8 bytes per displayed page, counting expanded newlines and localisation
substitutions. These are authoring limits, not a proven engine capacity.
The installed TFR source maximum found on 2026-09-07 was `atom.22.desc`:
4849 characters / 8816 UTF-8 bytes; `ptf.123.d` has 3774 / 6932 and `ptf.89.d`
3183 / 5802. Their complete in-game rendering was not verified; do not copy
8816 as a safe limit. A-Discord previously truncated a description at 6144 bytes.
Merge adjacent story pages when the result remains readable and meets both
ceilings; do not split solely to match an arbitrary page count. Shorten the
author's prose only when requested. See the focus-effects guide for evidence.
Group related sentences into paragraphs; do not insert a blank line after every
short sentence. Every page of a multi-event reading sequence must offer a full
exit that clears navigation state and does not dispatch another page. Keep
required gameplay settlement independent of optional reading navigation.
Keep required GUI children in the containers the engine looks up, even when
their visual positions change.
Scripted triggers use boolean calls (`trigger_name = yes/no`). Do not pass
scripted-effect macro arguments to them: the native loader loses subsequent
decisions after such a call. Reuse country-scoped predicates instead; a Python
test expander must not silently add syntax the game does not support.
Shared STP calculations take explicit temporary input variables and a boolean
effect call. Validate nested effect-call syntax in the native loader before
introducing argument blocks; static brace balance and test expansion do not
prove those calls load. Register mission IDs used by `days_mission_timeout@ID`
in the existing synchronized dynamic token file to keep multiplayer reads stable.
For missions, `available` is the success condition. A timeout-only mission must
use `available = { hidden_trigger = { always = no } }`; an empty goal succeeds
immediately and skips `timeout_effect`. `selectable_mission = no` does not prevent
automatic success. Verify the active countdown and the next scheduled mission.
Details and TFR examples belong in the existing
[focus-effects guide](docs/development/focus-effects.md).

## Performance

Before changing runtime performance, read the source-backed
[performance guide](docs/development/performance.md). Trace the caller,
frequency, scope, guards and consumers; distinguish recurring work from
one-time setup and bounded recovery. Country-scoped periodic hooks must not
wrap another world scan. Prefer tag-specific hooks for country-only work,
event-driven invalidation and bounded reconciliation for inputs without hooks.
Keep GUI preview work separate from simulation and AI policy calculations;
adding `dirty` requires covering every visible input, including observer and
player-country changes. Preserve exact resource accounting and deadlines.
Do not import reference-mod defines wholesale: verify native support, final
assignment and AI responsiveness. Speed settings, multiplayer lag thresholds
and fewer source files are not evidence of reduced CPU work. Report static
findings separately from measured campaign/UI performance; use comparable
before/after runs before claiming a speedup.
AI template and naval-goal country filters must be non-empty and contain only registered tags. An empty
`available_for` or `blocked_for` list can make the native loader consume the
following role and template fields as country tags. Keep one root definition
per role and check a cold-load log, not only the script parser. Production
minimums from all enabled strategies add together; count them against the
country's actual military factories and leave capacity for its basic weapons.

Registered tags, countries present on the map and scripted participants are
different sets. Before deleting or suppressing a country, run the minor validator
with `--inventory`, then inspect ownership/cores, OOB, subjects, future creation,
dynamic scopes and player handoff. A literal-reference inventory cannot prove
that a tag is unused. Keep dynamic civil-war tags and authored successor countries.
Minor suppression is not a native AI-off switch. Wake a suppressed country before
story participation or research-slot rewards; retain restoration for retired
allowlist entries. Its monthly player-takeover fallback is delayed until the next
pulse. Preserve the optimized guard, exact restoration slots and cleanup of stale
assistance ideas; never replace these with recurring world scans. See the country
lifecycle and verification contract in the performance guide.

## Verification

For focus rewards, see [the focus-effects guide](docs/development/focus-effects.md):
TFR source analysis, cumulative dynamic modifiers, dummy delta previews,
ownership across civil wars, and lifecycle checks for human authors and agents.

Run the focused test or validator for the paths changed, then run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
```

Static validation cannot prove Clausewitz runtime behavior. Fully restart
Hearts of Iron IV and inspect fresh logs after changes to loaded gameplay,
ideas, GFX, AI, defines, localisation names, or map data. Capture a fresh
campaign/UI result when the change is player-visible.
Record the loaded source hashes before a runtime check. In a shared checkout,
a hot reload during an open event invalidates that choice as evidence; restart
with the final files before drawing conclusions about its effects.

## Dirty worktrees

This repository is commonly an authoritative, dirty checkout. Preserve
unrelated work: inspect status first, avoid reset/checkout/bulk formatting,
and stage explicit verified paths only. Do not include someone else's changes
in a commit, and do not delete files unless their exact targets and purpose
have been verified.

##
не забывай, что здесь еще работать живым кодерам, поэтому держи кодстайл, оптимизацию и разделение на файлы (не делай лишние файлы, где можно сгруппировать)
