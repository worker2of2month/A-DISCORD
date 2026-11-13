# Команды суперсобытий A-Discord

Справочник содержит все 70 команд пространства имён `ADISCORD_superevent`:
69 отдельных презентаций и один выбор варианта ресурсной войны по мандату NAM.

## Как использовать

1. После обновления файлов мода полностью перезапустите игру и начните новую кампанию.
2. Откройте игровую консоль и введите нужную команду из таблицы без обратных кавычек.
3. Закройте консоль, чтобы посмотреть суперсобытие.
4. Если другое суперсобытие уже открыто, закройте его: следующий запрос ждёт в общей очереди.

Например, падение империи Хана:

```text
event ADISCORD_superevent.15
```

Копируйте пространство имён с указанным регистром: `ADISCORD_superevent`.
Звёздочка в записи `ADISCORD_superevent.*` обозначает семейство ID;
в самой команде вместо неё нужен конкретный номер из таблицы.
Номер события отличается от внутреннего номера запроса очереди.

Повторный запрос уже открытой или ожидающей карточки не добавляет ещё одну
копию в очередь. После закрытия карточку можно вызвать повторно.

## Особенности отдельных команд

- `.1` запускает настоящий распад Воркерланда, если он ещё не начался и страна
  существует. После начала распада команда повторно показывает презентацию.
- `.7` выбирает вариант ресурсной войны по текущему мандату NAM.
  Для точного выбора используйте `.29` (основной), `.30` (наместники)
  или `.31` (округа).
- `.25` при показе карточки запускает эффект портала на карте.
- Остальные команды показывают презентацию без применения соответствующего
  политического исхода: название победы само по себе не завершает войну.
- `.16` и `.22` отсутствуют. Единое суперсобытие падения империи Хана вызывается
  через `.15`; отдельной карточки смерти Хана нет.

## Полный список команд

Названия соответствуют русской локализации. Команды расположены по номеру.

| Команда | Суперсобытие |
| --- | --- |
| `event ADISCORD_superevent.1` | Гражданская война в Воркерланде |
| `event ADISCORD_superevent.2` | Возрождение Конфедерации |
| `event ADISCORD_superevent.3` | Утилитарная республика |
| `event ADISCORD_superevent.4` | Падение Периметра |
| `event ADISCORD_superevent.5` | Имперская реставрация |
| `event ADISCORD_superevent.6` | Воркеландское поле экспериментов |
| `event ADISCORD_superevent.7` | Ресурсная война: вариант по мандату NAM |
| `event ADISCORD_superevent.8` | Последняя империя |
| `event ADISCORD_superevent.9` | Провозглашено Кефрейтское содружество! |
| `event ADISCORD_superevent.10` | Провозглашён Великий Стеландер! |
| `event ADISCORD_superevent.11` | ИМПЕРИЯ ЧЁРНОГО ЗНАМЕНИ |
| `event ADISCORD_superevent.12` | ПОСЛЕДНЯЯ ИМПЕРИЯ |
| `event ADISCORD_superevent.13` | Вторая Иторско-Воркерландская война |
| `event ADISCORD_superevent.14` | Гражданская война в Иторе |
| `event ADISCORD_superevent.15` | Падение империи |
| `event ADISCORD_superevent.17` | ПОБЕДА СОТНИКОВА |
| `event ADISCORD_superevent.18` | ДИРЕКТОРИЯ МЕЧА |
| `event ADISCORD_superevent.19` | ГЕНЕРАЛ ПОД ХАРТИЕЙ |
| `event ADISCORD_superevent.20` | СТЕЛАНДСКИЙ СОЮЗ |
| `event ADISCORD_superevent.21` | МЕРА ОБЩЕГО БЛАГА |
| `event ADISCORD_superevent.23` | РОЖДЕНИЕ ВЕЧНОГО ИМПЕРИУМА |
| `event ADISCORD_superevent.24` | ПОБЕДА ЧРЕЗВЫЧАЙНОГО КОМИТЕТА |
| `event ADISCORD_superevent.25` | ПО ТУ СТОРОНУ МИРА |
| `event ADISCORD_superevent.26` | Провозглашение стеландского имперского союза! |
| `event ADISCORD_superevent.27` | Победа партии в Стеландере |
| `event ADISCORD_superevent.28` | Победа Шабрата в Стеландере |
| `event ADISCORD_superevent.29` | Ресурсная война |
| `event ADISCORD_superevent.30` | Ресурсная война: приказ наместников |
| `event ADISCORD_superevent.31` | Ресурсная война: ополчение округов |
| `event ADISCORD_superevent.32` | Высшие Дома правят Стеландером |
| `event ADISCORD_superevent.33` | Генералы Стеландера берут власть |
| `event ADISCORD_superevent.34` | Стеландская витрина снова открыта |
| `event ADISCORD_superevent.35` | Тишина над Стеландером |
| `event ADISCORD_superevent.36` | Нодрул празднует стеландскую победу |
| `event ADISCORD_superevent.37` | Праздник продолжается! |
| `event ADISCORD_superevent.38` | Концессия Конклава десяти |
| `event ADISCORD_superevent.39` | Хартии Южного договора |
| `event ADISCORD_superevent.40` | Юг под управлением Дирекции Нура |
| `event ADISCORD_superevent.41` | Раздел южных владений |
| `event ADISCORD_superevent.42` | Победа Коммуны огня |
| `event ADISCORD_superevent.43` | Конклав девяти удержал Юг |
| `event ADISCORD_superevent.44` | Наместничества Юга |
| `event ADISCORD_superevent.45` | Юг принимает Нефтяную хартию |
| `event ADISCORD_superevent.46` | Южные договоры Светлогорья |
| `event ADISCORD_superevent.47` | Возвращение южных портов |
| `event ADISCORD_superevent.48` | Материковый реванш |
| `event ADISCORD_superevent.49` | Юг под властью опор |
| `event ADISCORD_superevent.50` | Победа Свободных островов |
| `event ADISCORD_superevent.51` | Юг достался правлениям |
| `event ADISCORD_superevent.52` | Альянс удержал нефтяной пояс |
| `event ADISCORD_superevent.53` | Запад входит в Конфедерацию |
| `event ADISCORD_superevent.54` | Победа имперского Воркерланда |
| `event ADISCORD_superevent.55` | Восстановление Вейранской империи |
| `event ADISCORD_superevent.56` | Технический союз Форула |
| `event ADISCORD_superevent.57` | Запад Антона Багли |
| `event ADISCORD_superevent.58` | Победа Гуманистического щита |
| `event ADISCORD_superevent.59` | Чрезвычайная опека Иторы |
| `event ADISCORD_superevent.60` | Иторский реванш |
| `event ADISCORD_superevent.61` | Западный мир Комитета Иторы |
| `event ADISCORD_superevent.62` | Мировая империя Воркерланда |
| `event ADISCORD_superevent.63` | Железная лестница на Юге |
| `event ADISCORD_superevent.64` | Победа Служебной республики |
| `event ADISCORD_superevent.65` | Южные округа Федерации |
| `event ADISCORD_superevent.66` | Победа Нефтяного союза |
| `event ADISCORD_superevent.67` | Республика договоров на Юге |
| `event ADISCORD_superevent.68` | Победа Делового совета |
| `event ADISCORD_superevent.69` | Светлогорье выиграло войну за Юг |
| `event ADISCORD_superevent.70` | Запад под мандатом Чрезвычайного совета |
| `event ADISCORD_superevent.71` | Мировая империя Воркерланда победила Итору |
| `event ADISCORD_superevent.72` | Провозглашение Вейранской империи |
| `event ADISCORD_superevent.73` | Провозглашение государства Совета командиров; название соответствует выбранной идентичности Кефрейта |
| `event ADISCORD_superevent.74` | Война за Юг: начало войны с Шахрабадом |

## Проверка повторов

Смысловые пересечения, общие картинки и музыка перечислены в
[аудите дублей суперсобытий](../audits/superevent-duplicates.md).

## Где поддерживается список

- [Игровые определения событий](../../events/ADISCORD_superevents.txt).
- [Русские названия](../../localisation/russian/ADISCORD_superevents_l_russian.yml).
- [Реестр ID](../../tools/data/adiscord_event_ids.json).
- [Валидатор презентаций и консольных вызовов](../../tools/validators/validate_adiscord_superevents.py).

При добавлении презентации нужны отдельный вызов `ADISCORD_superevent.<номер>`,
запись в реестре и строка в этой таблице. Согласованность игровых определений
проверяется командами:

```powershell
python -B -m tools.validators.validate_adiscord_superevents
python -B -m tools.validators.validate_adiscord_event_ids
```

Статические проверки не заменяют ручную проверку показа в игре.
