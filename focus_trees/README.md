# Исходники фокусов

Редактируйте фокусы в этих папках:

- `STP/preparation` - подготовка и выбор стороны.
- `STP/civil_war` - гражданская война и общие части дерева.
- `STP/postwar/party` - послевоенная партия.
- `STP/postwar/shabrat` - общие послевоенные фокусы Шабрата, гегемония и директория.
- `STP/postwar/charter/sotnikov.txt` - правительство Хартии Сотникова.
- `STP/postwar/charter/shabrat.txt` - правительство Хартии Шабрата.
- `STP/postwar/charter/tikhoreva.txt` - правительство Хартии Тихоревой.
- `STP/postwar/focuses.txt` - изгнание и возвращение через Нодрул.
- `VAL/main`, `VAL/defeated`, `VAL/administration` - деревья Кефрейта.
- `RUS/main` - дерево Руси.
- `Vorkerland/prewar` - довоенный WRK и автономии; собирается как общая история фокусов,
  дерево WKR подключает её корень WRK.
- `Vorkerland/wkr`, `Vorkerland/vad`, `Vorkerland/tva` - претенденты гражданской войны.
- `Vorkerland/settlement` - объединённый WRK: рабочее, совместное и техническое урегулирование.
- `Vorkerland/worker_confederation`, `Vorkerland/technical_directorate`,
  `Vorkerland/world_empire` - послевоенные деревья маршрутов.
- `Vorkerland/iba_norvane`, `Vorkerland/zao` - региональные деревья Воркерланда.
- `shared/generic`, `shared/bookmark` - общие деревья.

После правок соберите игровые файлы из корня мода:

```powershell
python -B -m tools.builders.build_adiscord_focus_trees --check
python -B -m tools.builders.build_adiscord_focus_trees --apply
python -B -m tools.builders.build_adiscord_focus_trees --check
```

Сборщик записывает файлы непосредственно в `common/national_focus`.
Их исходники указаны в заголовках. Формат включения фрагментов описан в
[руководстве по фокусам](../docs/development/focus-effects.md).

Каждый файл кабинета Хартии содержит всю его программу из 25 фокусов.
Порядок включения задаёт `STP/civil_war/focuses.txt`. Все эти ветви входят
в одно игровое дерево `STP_cw_focus`; служебные строки `@section` и `@include`
обрабатывает сборщик. Вложенные включения во фрагментах не используются.
