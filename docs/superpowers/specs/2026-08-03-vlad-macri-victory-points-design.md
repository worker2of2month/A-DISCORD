# Victory points for Vlad Macri's Republic of Ebern

## Goal

Make the territory assigned to Vlad Macri's Republic of Ebern after the Vorkerland collapse visibly and strategically developed. Add a clear capital VP and a distributed network of small settlement VPs, including the missing city shown in state 313.

## Scope

The collapse setup transfers states 197 and 311-314 to EBA. The change covers only victory points in those states, their Russian localisation, generator ownership, and validation. Existing population, buildings, resources, borders, ownership, and collapse logic stay unchanged.

## VP layout

- State 197: raise Ebern, province 10016, from 5 to 10 VP. It remains EBA's capital.
- State 312: add Noyen, urban province 16637, as a 3 VP secondary city.
- State 313: add Estervik, urban province 16617, as a 3 VP secondary city. This is the missing city visible in the supplied screenshot.
- State 311: add Felden, province 5905, as a 1 VP railway-junction settlement. Province 5905 joins three local rail routes.
- State 314: add Linden, province 5405, as a 1 VP railway settlement on the route leading south-west from Estervik.

The Russian visible names are `Фельден` and `Линден`. Both provinces are non-urban terrain and will be explicitly registered as approved non-urban settlements rather than weakening the general validator.

## Data ownership

`tools/build_adiscord_new_states.py` remains authoritative. Urban VPs in states 312-313 stay in `VORKERLAND_CENTRES`; the two explicit 1 VP railway settlements use a separate non-urban Vorkerland settlement mapping consumed by `render_state`. This keeps the exception narrow and inspectable. Legacy state 197 remains managed by `VORKERLAND_LEGACY_VICTORY_POINTS`. Generated VP names remain in `GENERATED_VICTORY_POINT_NAMES` and are written to the BOM-safe Russian VP localisation file.

The corresponding generated state files and localisation output will be updated to match the generator without running broad destructive regeneration over unrelated dirty work.

## Validation

A focused regression test will first assert the complete EBA VP layout and fail against the current data. The implementation will then update the generator and generated outputs until the focused test passes. Final verification will run the focused Vorkerland/new-state checks, `python -B tools/validate_tc.py --limit 300`, and `git diff --check` on the scoped changes.

Static validation proves data wiring, province membership, localisation coverage, and generator consistency. Final in-game placement still requires a fresh game or screenshot because static checks cannot prove visual map placement.
