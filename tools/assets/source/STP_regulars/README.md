# Пехота и штабы A-Discord

Десять пехотных комплектов используют штатный 33-костный скелет и собственное снаряжение.
Исходные пользовательские mesh/DDS сохраняются. Страны и основы дополнительных
семейств перечислены в `factions.json`.

| Комплект | Основа | Вид |
| --- | --- | --- |
| STP_party | Существующее тело STP | Олива, броня со скошенными углами, парные подсумки, защита голеней |
| STS_regular | Существующее тело STP | Серо-синяя форма, мягкая песочная разгрузка, широкие лямки, охристая повязка |
| VAL_regular | Существующее тело STP | Полукамуфляж, каска, балаклава, самая тяжёлая разгрузка с боковыми карманами |
| WRK_line | GER | Оливково-охристый комплект Воркера для WRK/WKR |
| TVA_technical | USA | Серо-синий технический комплект доктора Воркса |
| VAD_line | FRA | Угольная форма с бордовыми деталями Вадла |
| WRK_fragment | eastern_european | Общая оливково-серая форма 35 осколков Воркерланда |
| IVN_line | ENG | Песочно-оливковый комплект Иторы с бирюзовыми деталями |
| NOD_line | USA | Сине-серая полевая куртка, брюки с карманами, каска с затылочной защитой, компактная разгрузка и рация |
| SRP_highland | ENG | Оливковая горная форма Окцидии, полевой головной убор, походный рюкзак и верёвка |

Износ ограничен фактурой ткани, швами и складками; белые пятна краски отсутствуют.
Подсумки имеют выпуклую тканевую оболочку и отдельные клапаны.

## Подключение

`package_regulars.py` владеет своими секциями в `ADISCORD_country_infantry.gfx`
и `zz_ADISCORD_country_infantry.asset`, а также каталогом
`gfx/models/units/ADISCORD_regulars`. Пакет: 10 mesh, 60 DDS и 2 реестра.

Для STP, STS и VAL семейство `infantry` использует регулярное тело, а
`ADISCORD_militia` — соответствующее исходное тело лёгких частей. Оба семейства
охватывают восемь поколений общего оружия. Остальные семь комплектов также имеют
восемь уровней и алиасы стран из `factions.json`. Алиас
`ADISCORD_VAL_regular_entity` нужен потребителям с явным `override_model`.
NOD использует `NOD_line`; SRP — `SRP_highland` для пехоты, ополчения и горных
частей. Состав и параметры шаблонов не меняются.

У NOD отдельные группы ожидания и обучения. Они исключают курение с оружием
поперёк нагрудной разгрузки и отжимания на наклонном рельефе. Стоячие упражнения
используют соответствующий поколению оружия rifle/MG-хват; остальные страны
сохраняют свои группы состояний.

## Командиры HQ

`headquarters.json` задаёт пять вариантов: оливковый партийный офицер STP
с фуражкой, сине-серый командир STS в берете, полукамуфляжный VAL в каске
с гарнитурой, NOD в полевой шляпе и нейтральный офицер для остальных стран.
Все используют штатное тело `generic_army_headquarters`, его локаторы,
33 кости, 16 зарегистрированных анимаций и масштаб entity 0.8.
Пистолет, винтовка, карандаш, планшет и бинокль сохраняют штатные крепления.

`package_headquarters.py` владеет 5 mesh, 30 DDS, двумя HQ-реестрами и
`gfx/interface/equipmentdesigner/graphic_db/ADISCORD_army_headquarters.txt`.
Последний содержит только модельные пулы `hq_support_company`: общий весом
1000 и четыре страновых весом 3000. Он нужен при отключённой через
`replace_path` ванильной graphic_db. Доступность HQ зависит от существующего
определения подразделения и DLC; пакет моделей не меняет это условие.

Крепления оружия и скрытие неактивных вариантов следуют штатным анимациям.
У VAL локатор дыма различается между исходным и регулярным скелетом;
`repair_val_idle.py` сохраняет правильный узел для каждого тела.

## Сборка

`build_regulars.py` строит первые три комплекта из `../STP_shabrat/STP.blend`.
`build_factions.py` использует ванильные основы остальных семи.
`build_headquarters.py` строит пять офицерских комплектов.
`*_body_source.png` — UV-текстуры тела; карты снаряжения запекаются из текущей
геометрии и материалов. Повторная генерация изображений не требуется.

Из корня мода:

```powershell
& 'D:\steam\steamapps\common\Blender\blender.exe' -b -t 4 --python-exit-code 1 --python tools/assets/source/STP_regulars/build_regulars.py
& 'D:\steam\steamapps\common\Blender\blender.exe' -b -t 4 --python-exit-code 1 --python tools/assets/source/STP_regulars/build_factions.py
python -B tools/assets/source/STP_regulars/package_regulars.py --prepare
& 'D:\steam\steamapps\common\Blender\blender.exe' -b -t 4 --python-exit-code 1 --python tools/assets/source/STP_regulars/export_verify.py
python -B tools/assets/source/STP_regulars/package_regulars.py
python -B tools/assets/source/STP_regulars/package_regulars.py --apply
python -B tools/assets/source/STP_regulars/package_regulars.py --check
```

HQ собираются отдельно через `build_headquarters.py`, затем
`package_headquarters.py --prepare` и `export_verify.py -- STP_hq STS_hq VAL_hq NOD_hq generic_hq`.
Перед установкой выполняется `package_headquarters.py --preview <каталог вне мода>`,
после — `--apply` и `--check`. `verify_headquarters.py --staging <каталог>`
повторно импортирует экспорт и проверяет каждый кадр всех командных клипов,
включая видимость и геометрию семи аксессуаров. Запускать через Blender с
`--python-exit-code 1`. `export_verify.py -- --verify <HQ-комплекты>` использует
эту же проверку для установленного пакета.

Для частичной пересборки Blender-скриптам передают имена комплектов после `--`,
а подготовке карт — после `--labels`. Экспорт сохраняет нативные локаторы,
нормированные веса и не более четырёх влияний на вершину. `*_export.json`
содержит фактическое число треугольников и результаты проверки.

Тело и снаряжение используют отдельные материалы `PdxMeshAdvanced`.
DDS имеют mip-уровни до 1×1. Normal хранит tangent X в G, инвертированный Y
в A; specular — силу отражения в G, металличность в B и gloss в A.
Normal снаряжения содержит запечённый рельеф ткани; normal тела — от основы.

## Просмотр

`python -B tools/assets/source/jorodox_preview_server.py` запускает локальный стенд.
Страница `http://127.0.0.1:8767/?batch=infantry` создаёт 20 кадров в
`jorodox_visual/` загрузчиками установленного JoroDox 0.8.1. Проверка:
`python -B tools/assets/source/verify_jorodox_visual.py --family infantry`.
Для отдельного пакета серверу и проверке передают `--infantry-root`.
Для HQ используются `?batch=hq`, `--family hq` и `--hq-root`; создаются 10 кадров.
Включён FrontSide; каждый кадр содержит хеши mesh/DDS и результат WebGL.

Это просмотр файлов с Phong fallback, а не игровой shader. Скелет, крепления
и позы проверяются отдельно после повторного импорта native mesh/anim.
Автоматический выбор слабой/сильной формы, освещение и масштаб на карте требуют
отдельной проверки окончательного пакета в HOI4.
