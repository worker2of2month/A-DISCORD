# Development

Документ описывает механику развития страны в моде A-Discord.

## Списки стран

Списки лежат в `common/scripted_triggers/ADISCORD_development_country_lists.txt`.

`ADISCORD_is_playable_development_country` - страны, для которых development является основной механикой и показывается в интерфейсе политики.

Сейчас в playable-списке:
- `VAL`
- `STP`
- `WRK`

`ADISCORD_is_secondary_development_country` - второстепенные страны. Playable-страны физически исключены из этого списка, чтобы не было двойного тика и лишних проверок.

## Частота обновления

Playable-страны обновляются каждый месяц через `on_monthly`:

```txt
ADISCORD_tick_all_society_development_monthly = yes
```

Secondary-страны обновляются раз в год через `on_yearly`, только если страна контролируется ИИ:

```txt
ADISCORD_tick_all_society_development_yearly = yes
```

Годовой тик делает 12 progress-only шагов подряд, затем один раз пересчитывает общий уровень страны. Это дороже прямого умножения, но корректно обрабатывает повышение и понижение уровней, потому что каждый переход уровня сбрасывает прогресс.

## Показатели

Есть 6 показателей:
- `society`
- `social_system`
- `army`
- `cultural`
- `state`
- `economic`

У каждого показателя есть три основные переменные:
- `ADISCORD_<type>_development_level` - уровень от 1 до 5.
- `ADISCORD_<type>_development_progress` - прогресс до следующего уровня от -99 до 99.
- `ADISCORD_<type>_development_monthly_growth` - месячный прирост в очках.

100 очков прогресса повышают уровень на 1. -100 очков прогресса понижают уровень на 1.

## Прирост

Система использует один итоговый прирост на показатель: `ADISCORD_<type>_development_monthly_growth`.

Разделение на `base/focus/event/decision/modifier` убрано ради простоты и меньшего числа операций на регулярных тиках.

Пример изменения прироста фокусом, событием или решением:

```txt
add_to_variable = { var = ADISCORD_society_development_monthly_growth value = 2 }
clamp_variable = { var = ADISCORD_society_development_monthly_growth min = -20 max = 20 }
```

Debug-решения используют scripted effects:

```txt
ADISCORD_increase_society_development_monthly_growth = yes
ADISCORD_decrease_society_development_monthly_growth = yes
```

Ограничение по умолчанию: от `-20` до `20` очков в месяц.

## Прогресс-бар

Прогресс-бар в интерфейсе завязан на `ADISCORD_<type>_development_progress`, а не на уровень.

Видимые состояния:
- `< 20` - пустой бар.
- `20-39` - 25%.
- `40-59` - 50%.
- `60-79` - 75%.
- `80+` - 100%.

Иконка показателя зависит от текущего уровня.

## Общий уровень страны

Общий уровень пересчитывается эффектом:

```txt
ADISCORD_update_total_country_development = yes
```

Переменные:
- `ADISCORD_total_development_score` - сумма 6 уровней, диапазон 6-30.
- `ADISCORD_total_development_level` - общий уровень страны от 1 до 5.

Порог общего уровня:
- 1: сумма 6-11.
- 2: сумма 12-17.
- 3: сумма 18-23.
- 4: сумма 24-29.
- 5: сумма 30.

Scripted triggers:

```txt
ADISCORD_country_development_exact_1 = yes
ADISCORD_country_development_at_least_3 = yes
ADISCORD_country_development_at_most_4 = yes
```

Эти triggers можно использовать в фокусах, решениях и событиях.

## Интерфейс

Блок development в `interface/ADISCORD_CountryView.gui` показывается только для стран из `ADISCORD_is_playable_development_country`.

Строка роста имеет тултип, который показывает:
- месячный прирост;
- текущий прогресс до следующего уровня.

## Ключевые файлы

- `common/scripted_triggers/ADISCORD_development_country_lists.txt` - списки playable/secondary.
- `common/on_actions/00_ADISCORD_on_actions.txt` - месячный и годовой тик.
- `common/scripted_effects/ADISCORD_society_development_effects.txt` - уровни, прогресс, рост, общий уровень.
- `common/scripted_triggers/ADISCORD_society_development_triggers.txt` - triggers уровней, прогресс-бара и общего уровня.
- `common/scripted_guis/CountryView_ScriptedGui.txt` - видимость UI-элементов.
- `interface/ADISCORD_CountryView.gui` - интерфейс блока development.
