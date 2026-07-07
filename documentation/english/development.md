# Development

This document describes the country development system in A-Discord.

## Country Lists

Country lists are defined in `common/scripted_triggers/ADISCORD_development_country_lists.txt`.

`ADISCORD_is_playable_development_country` marks countries that use development as a primary mechanic and can see the development block in the politics interface.

Current playable countries:
- `VAL`
- `STP`
- `WRK`

`ADISCORD_is_secondary_development_country` marks secondary countries. Playable countries are physically excluded from this list to avoid double ticking and extra checks.

## Update Frequency

Playable countries update every month through `on_monthly`:

```txt
ADISCORD_tick_all_society_development_monthly = yes
```

Secondary countries update once per year through `on_yearly`, only when controlled by AI:

```txt
ADISCORD_tick_all_society_development_yearly = yes
```

The yearly tick runs 12 progress-only steps, then recalculates total country development once. This is more expensive than direct multiplication, but it correctly handles level gains and losses because each level transition resets progress.

## Metrics

There are 6 metrics:
- `society`
- `social_system`
- `army`
- `cultural`
- `state`
- `economic`

Each metric has three main variables:
- `ADISCORD_<type>_development_level` - level from 1 to 5.
- `ADISCORD_<type>_development_progress` - progress toward the next level, from -99 to 99.
- `ADISCORD_<type>_development_monthly_growth` - monthly growth in progress points.

100 progress points increase the level by 1. -100 progress points decrease the level by 1.

## Growth

The system uses one final growth variable per metric: `ADISCORD_<type>_development_monthly_growth`.

The earlier `base/focus/event/decision/modifier` split was removed to keep the system simpler and reduce work during regular ticks.

Example growth change from a focus, event, or decision:

```txt
add_to_variable = { var = ADISCORD_society_development_monthly_growth value = 2 }
clamp_variable = { var = ADISCORD_society_development_monthly_growth min = -20 max = 20 }
```

Debug decisions use scripted effects:

```txt
ADISCORD_increase_society_development_monthly_growth = yes
ADISCORD_decrease_society_development_monthly_growth = yes
```

Default clamp: from `-20` to `20` points per month.

## Progress Bar

The interface progress bar is tied to `ADISCORD_<type>_development_progress`, not to the current level.

Visible states:
- `< 20` - empty bar.
- `20-39` - 25%.
- `40-59` - 50%.
- `60-79` - 75%.
- `80+` - 100%.

The metric icon still depends on the current level.

## Total Country Development

Total development is recalculated by:

```txt
ADISCORD_update_total_country_development = yes
```

Variables:
- `ADISCORD_total_development_score` - sum of all 6 levels, range 6-30.
- `ADISCORD_total_development_level` - total country development level from 1 to 5.

Total level thresholds:
- 1: score 6-11.
- 2: score 12-17.
- 3: score 18-23.
- 4: score 24-29.
- 5: score 30.

Scripted triggers:

```txt
ADISCORD_country_development_exact_1 = yes
ADISCORD_country_development_at_least_3 = yes
ADISCORD_country_development_at_most_4 = yes
```

These triggers can be used in focuses, decisions, and events.

## Interface

The development block in `interface/ADISCORD_CountryView.gui` is visible only to countries in `ADISCORD_is_playable_development_country`.

The growth line tooltip shows:
- monthly growth;
- current progress toward the next level.

## Key Files

- `common/scripted_triggers/ADISCORD_development_country_lists.txt` - playable/secondary lists.
- `common/on_actions/00_ADISCORD_on_actions.txt` - monthly and yearly ticks.
- `common/scripted_effects/ADISCORD_society_development_effects.txt` - levels, progress, growth, total level.
- `common/scripted_triggers/ADISCORD_society_development_triggers.txt` - level, progress bar, and total level triggers.
- `common/scripted_guis/CountryView_ScriptedGui.txt` - UI element visibility.
- `interface/ADISCORD_CountryView.gui` - development block interface.
