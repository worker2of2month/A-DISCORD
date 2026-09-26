# Исходники фокусов

Редактируйте фокусы в этих папках:

- `STP/preparation` — подготовка и выбор стороны.
- `STP/civil_war` — гражданская война и общие части дерева.
- `STP/postwar/party` — послевоенная партия.
- `STP/postwar/shabrat` — послевоенный Шабрат.
- `STP/postwar/focuses.txt` — изгнание и возвращение через Нодрул.
- `VAL/main`, `VAL/defeated`, `VAL/administration` — деревья Кефрейта.
- `RUS/main` — дерево Руси.
- `Vorkerland/civil_war`, `Vorkerland/iba_norvane`, `Vorkerland/zao` — деревья Воркерланда.
- `shared/generic`, `shared/bookmark` — общие деревья.

После правок соберите игровые файлы из корня мода:

```powershell
python -B -m tools.builders.build_adiscord_focus_trees --check
python -B -m tools.builders.build_adiscord_focus_trees --apply
python -B -m tools.builders.build_adiscord_focus_trees --check
```

Сборщик записывает файлы непосредственно в `common/national_focus`.
Их исходники указаны в заголовках. Формат включения фрагментов описан в
[руководстве по фокусам](../docs/development/focus-effects.md).
