# A-Discord Law Localisation Redesign

**Date:** 2026-08-16

**Status:** Approved design, pending written-spec review

**Scope:** Player-facing Russian and English localisation for global laws

## Goal

Make the mod's laws read like credible political, economic, military, and social institutions. Remove artificial bureaucratic phrasing, slogans, unnecessary drama, and technical implementation language without changing gameplay.

The desired register is restrained historical realism: clear enough for the law-selection interface, specific enough to explain the institution, and neutral enough to work for every country using the global law key.

## Non-goals

This change does not alter:

- law category IDs, membership, or order;
- technical law IDs;
- modifiers, costs, availability, AI weights, or removal rules;
- starting law packages in country history;
- country-specific lore or flavour;
- interface layout or law icons.

## Editorial standard

### Names

- Preserve names that already sound natural, including `Кадровая армия`, `Прогрессивная шкала`, and `Государственные больницы`.
- Rename only artificial, imprecise, overly literary, or unnecessarily technical entries.
- Prefer two to four words naming a recognisable institution, policy, or administrative practice.
- Avoid slogans, metaphors, implied moral judgement, and invented futuristic bureaucracy.
- Do not use a country-specific term in a shared global key.

### Descriptions

Review every law description, but edit only descriptions that violate the agreed register.

Each revised description should normally contain two compact ideas:

1. how the institution or policy works;
2. the practical trade-off it creates.

Descriptions must not:

- reproduce modifier values in prose;
- use developer-facing language such as `vanilla-модификаторы`;
- read like propaganda, advertising, or a moral verdict;
- rely on metaphors such as "страна хуже дышит";
- claim mechanics the law does not actually provide.

Russian localisation defines the editorial tone. English localisation must express the same meaning in natural English rather than translate Russian phrasing word for word.

The custom laws in `ADISCORD_laws.txt` currently have Russian localisation but no matching English localisation file. Adding English name and description entries for those existing keys is explicitly part of this localisation redesign. It does not authorise new law IDs or gameplay content.

## Approved civilian and economic names

Only listed entries are renamed. Unlisted law names remain unchanged.

| Current Russian name | Approved Russian name |
|---|---|
| Тип общества | Общественный уклад |
| Индустриализирующаяся экономика | Экономика индустриализации |
| Государственно-координируемая экономика | Государственно регулируемая экономика |
| Планово-бюрократическая экономика | Административно-плановая экономика |
| Кланово-олигархическая экономика | Клановая экономика |
| Открытая пресса | Свободная пресса |
| Лицензированная пресса | Регулируемая пресса |
| Государственные сводки | Государственная пресса |
| Запечатанные сети | Государственный контроль информации |
| Децентрализованные сборы | Местное налогообложение |
| Единый налоговый реестр | Единая налоговая система |
| Промышленные тарифы | Протекционистские тарифы |
| Квотное изъятие | Чрезвычайные сборы |
| Базовые службы помощи | Базовая социальная помощь |
| Всеобщее обеспечение | Всеобщие социальные гарантии |
| Нормированная поддержка | Военное нормирование |
| Неформальное обучение | Местное образование |
| Гражданская программа | Гражданское образование |
| Базовые клиники | Первичная медицинская помощь |
| Терпимые субкультуры | Культурный плюрализм |
| Публичные развлечения | Массовая культура |
| Гражданские фестивали | Общественные праздники |
| Покровительство авангарду | Поддержка современного искусства |
| Национальное мифотворчество | Патриотическая культурная политика |
| Ремесленные рынки | Ремесленное производство |
| Сбалансированные мастерские | Поддержка частного производства |
| Гражданское расширение | Приоритет гражданской промышленности |
| Военный приоритет | Приоритет военной промышленности |
| Плановые комитеты | Промышленное планирование |
| Свободные контракты | Гибкая занятость |
| Цеховая защита | Профессиональные объединения |
| Регулируемые смены | Трудовое регулирование |
| Технократические нормы труда | Научная организация труда |
| Мобилизованный труд | Трудовая мобилизация |
| Лоскутные дороги | Местное дорожное хозяйство |
| Региональные дорожные работы | Региональные инфраструктурные программы |

## Approved military and security names

Only listed entries are renamed. Unlisted law names remain unchanged.

| Current Russian name | Approved Russian name |
|---|---|
| Автономные ополчения | Территориальное ополчение |
| Контрактные бригады | Контрактная служба |
| Штабная вертикаль | Централизованное командование |
| Сеть тотальной обороны | Система территориальной обороны |
| Местная выслуга | Продвижение по выслуге |
| Комиссии по заслугам | Отбор по профессиональным качествам |
| Чрезвычайные повышения | Повышения военного времени |
| Местное фуражирование | Снабжение за счёт местных ресурсов |
| Гражданские контракты | Гражданские поставщики |
| Централизованные склады | Централизованная система снабжения |
| Нерегулярные сборы | Периодические военные сборы |
| Стандартизированная программа | Единая программа подготовки |
| Офицерские штабные игры | Командно-штабные учения |
| Ускоренные лагеря подготовки | Ускоренная военная подготовка |
| Соседский надзор | Добровольные патрули |
| Местные гарнизоны | Территориальные гарнизоны |
| Следственные бюро | Политическая полиция |
| Внутренний директорат безопасности | Государственная служба безопасности |

`Политическая полиция` is intentionally explicit. The current law description covers political intelligence and suppression of organised disloyalty, so a generic investigative label would conceal the institution's actual function.

## Description examples

These examples define the intended voice. Final text may be adjusted for accuracy after checking each law's actual modifiers and availability conditions.

### Военная цензура

В военное время публикация сведений о потерях, снабжении и действиях армии ограничивается. Это помогает сдерживать панику и защищать военную информацию, но ослабляет политическую открытость.

### Чрезвычайные сборы

Государство вводит обязательные денежные и натуральные поставки. Казна и приоритетные отрасли быстрее получают необходимые ресурсы, однако нагрузка на население и хозяйство возрастает.

### Политическая полиция

Специальные органы расследуют деятельность организованной оппозиции и политически неблагонадёжных групп. Внутренний контроль усиливается вместе с полномочиями репрессивного аппарата.

## Implementation boundaries

The implementation pass must first map every approved Russian name to its existing localisation key. It must then inspect the matching law definition before revising the description so that the prose remains faithful to modifiers and availability.

Russian localisation files must remain UTF-8 with a BOM. English and Russian key sets must stay aligned. Generated localisation, if any selected key is generator-owned, must be changed through its owning builder and regenerated rather than hand-edited.

## Verification

The implementation is complete only when all of the following hold:

- every approved rename appears under the correct existing key;
- all retained names remain unchanged;
- revised descriptions follow the editorial standard and match the law mechanics;
- Russian localisation retains its UTF-8 BOM;
- Russian and English law keys remain aligned;
- `python -B -m unittest tools.tests.test_adiscord_economy_weekly_contracts` passes for the shared law and economy contracts;
- `python -B tools/validate_tc.py --limit 300` passes;
- both unstaged and cached `git diff --check` pass for the implementation scope;
- a full Hearts of Iron IV restart and fresh law-screen inspection confirm loading, line wrapping, and player-visible presentation.

Static validation alone does not establish the final in-game result.
