# A-DISCORD Superevents Cleanup Design

Date: 2026-09-17
Status: approved in chat for implementation planning

## Goal

Make the super-event subsystem predictable, easy to extend, and easy to audit without changing gameplay outcomes, timing, or existing public event IDs.

The cleanup must preserve the working Vorkerland civil-war and Stelander Imperial Union patterns: gameplay state changes remain owned by gameplay code, while the super-event subsystem owns presentation, display flags, UI, localisation, and audio dispatch.

## Current problems

1. `events/ADISCORD_news.txt` is misnamed and currently owns the `ADISCORD_superevent`, `ADISCORD_superevent_audio`, and `ADISCORD_superevent_news` namespaces.
2. Super-event presentation is distributed across GUI, GFX, scripted GUI, scripted localisation, localisation, sound assets, and gameplay effects without one enforced inventory/order.
3. Validators and the event-ID registry hard-code `events/ADISCORD_news.txt`, so simply moving the file would break repository contracts.
4. Formatting and ordering differ between the presentation files, making it difficult to compare the same super-event across layers.
5. The subsystem is being actively extended. Commit `588bf4f` made the Vorkerland utilitarian victory a real super-event, so the cleanup must preserve it rather than treating the old GUI window as dead code.

## Canonical ownership

### Event definitions

Create `events/ADISCORD_superevents.txt` as the sole owner of these namespaces:

- `ADISCORD_superevent`
- `ADISCORD_superevent_audio`
- `ADISCORD_superevent_news`

Move the complete current contents of `events/ADISCORD_news.txt` there without renumbering or changing the behaviour of existing IDs. Remove `events/ADISCORD_news.txt` after all references, tests, and registry ownership records are migrated.

`ADISCORD_superevent.1` and `ADISCORD_superevent.2` remain compatibility gateways because existing gameplay/debug code calls them directly.

### Gameplay ownership

Super-events must not become owners of gameplay mutations.

Examples:

- The Vorkerland collapse and Unity Tower destruction remain owned by the Vorkerland collapse subsystem. The civil-war super-event only presents the result/start to the player.
- The Stelander Imperial Union remains mechanically formed by `STP_proclaim_imperial_union`; its super-event/news route is presentation-only.
- The Dirty Zone reveal lifecycle, smoke cleanup, state hand-offs, and its ordinary major news event remain in the Vorkerland Dirty Zone subsystem. Only the dedicated super-event presentation assets/flag belong to the generic super-event presentation layer.
- Vorkerland victory selection remains owned by Vorkerland gameplay effects; those effects choose which presentation flag/event to dispatch.

## Active presentation inventory

The cleanup must preserve all currently active presentation routes:

1. `superevent_vorkerland_civilwar`
2. `superevent_vorkerland_dirty_opening`
3. `superevent_vorkerland_worker_victory`
4. `superevent_vorkerland_utilitarian_victory`
5. `superevent_vorkerland_vlad_victory`
6. `superevent_vorkerland_dorian_victory`
7. `superevent_stelander_empire`

The joint-government Vorkerland victory remains a localisation variant selected while the Vlad presentation flag is active; it is not a separate window unless gameplay later introduces a separate flag/window contract.

## Canonical ordering

Use this order wherever the same inventory is represented:

1. Vorkerland Civil War
2. Dirty Zone Opening
3. Worker Victory
4. Utilitarian Victory
5. Vlad / Joint-Government Victory
6. Dorian Victory
7. Stelander Imperial Union

Apply the order consistently to:

- `events/ADISCORD_superevents.txt` where applicable
- `interface/superevents.gfx`
- `interface/superevents.gui`
- `common/scripted_guis/superevents.txt`
- `common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt`
- `localisation/english/ADISCORD_superevents_l_english.yml`
- `localisation/russian/ADISCORD_superevents_l_russian.yml`
- `sound/superevents_sound.asset`
- `sound/superevents_effects.asset`
- `sound/superevents_category.asset`

Shared frame/button sprites remain before the per-event sprites.

## Naming and compatibility rules

- Do not renumber existing event IDs.
- Do not rename existing gameplay-facing global flags unless a proven bug requires it.
- Do not change console compatibility behaviour for `ADISCORD_superevent.1` or `.2`.
- Preserve existing art and sound asset paths unless a path is demonstrably wrong.
- Keep RU/EN localisation keys stable.
- Preserve the current human-player scoped audio routing needed by HOI4 major-news/global-effect scopes.
- Do not duplicate gameplay mutations inside presentation events.

## Formatting cleanup

Normalize the presentation files while touching them:

- one consistent indentation style;
- readable multi-line blocks instead of mixed one-line and expanded definitions where practical;
- consistent blank-line separation between super-events;
- comments only where they explain scope/ownership or an engine-specific constraint;
- remove stale comments that describe superseded behaviour.

This is a targeted cleanup. Do not refactor unrelated Vorkerland, STP, world-news, or general GUI systems.

## Registry and validator migration

Update `tools/data/adiscord_event_ids.json` so the six existing `ADISCORD_superevent*` event IDs point to `events/ADISCORD_superevents.txt`.

Update every validator/test that currently hard-codes `events/ADISCORD_news.txt`, including the Vorkerland collapse/story and Stelander Empire coverage.

Add a dedicated structural super-event contract test/validator that checks, for every active presentation inventory entry:

- exactly one scripted-GUI entry exists;
- exactly one GUI window exists;
- exactly one GFX sprite exists;
- title/quote/comment scripted-localisation routing exists;
- referenced title/quote/comment localisation keys exist in RU and EN;
- any declared dedicated sound effect resolves through sound effect -> sound asset -> category;
- no GUI/GFX/scripted-GUI presentation entry exists without being part of the declared active inventory, except explicitly documented shared infrastructure;
- the legacy `events/ADISCORD_news.txt` path no longer owns super-event IDs after migration.

The validator should be data-driven enough that adding a future super-event requires adding one inventory entry rather than scattering new assertions throughout multiple tests.

## Verification

Before the implementation commit is considered complete:

1. Run the dedicated super-event tests/validator.
2. Run the existing Vorkerland collapse validator/tests.
3. Run the existing Vorkerland story tests that reference super-events.
4. Run the Stelander Imperial Union super-event tests.
5. Run the event-ID registry validation if available.
6. Search the repository for stale `events/ADISCORD_news.txt` references.
7. Search for each active super-event flag across GUI/GFX/scripted localisation and verify the inventory is complete.
8. Review the final diff to ensure no gameplay/balance changes slipped into the presentation cleanup.

## Success criteria

The work is complete when:

- all generic super-event event definitions live in `events/ADISCORD_superevents.txt`;
- `events/ADISCORD_news.txt` is removed;
- presentation files use one canonical order and consistent formatting;
- current Vorkerland and Stelander presentation behaviour remains intact, including the newly added utilitarian route;
- Dirty Zone gameplay/news ownership remains separate from its super-event presentation;
- event registry and validators agree with the new ownership;
- structural validation prevents future orphaned or partially wired super-events;
- all relevant regression tests pass.
