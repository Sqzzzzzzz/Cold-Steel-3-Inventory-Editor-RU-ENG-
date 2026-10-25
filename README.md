<div align="center">

# Cold Steel III Inventory Editor

**Unofficial save inventory editor for _The Legend of Heroes: Trails of Cold Steel III_**  
**Неофициальный редактор инвентаря сохранений для _The Legend of Heroes: Trails of Cold Steel III_**

![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Languages: RU / EN](https://img.shields.io/badge/Interface-RU%20%7C%20EN-5667A3)
[![License: MIT](https://img.shields.io/badge/License-MIT-2D8659)](LICENSE)

**[Русский](#русский) · [English](#english) · [Скриншоты / Screenshots](#скриншоты--screenshots)**

</div>

## Скриншоты / Screenshots

**Русский интерфейс · Тёмная тема / Russian UI · Dark theme**

<p align="center">
  <img src="docs/screenshots/01-russian-dark.png" alt="Cold Steel III Inventory Editor — русский интерфейс, тёмная тема, мастер-кварцы" width="940">
</p>

**English UI · Light theme / Английский интерфейс · Светлая тема**

<p align="center">
  <img src="docs/screenshots/02-english-light.png" alt="Cold Steel III Inventory Editor — English interface, light theme, item search" width="940">
</p>

<details>
<summary><strong>Multi-select / Множественный выбор — ещё один скриншот</strong></summary>

<p align="center">
  <img src="docs/screenshots/03-multi-select.png" alt="Selecting multiple master quartz items for batch editing" width="940">
</p>

</details>

> Screenshots show the actual application with a demo save and locally available game data. Available item names and icons depend on the user's game installation.  
> На скриншотах показана настоящая программа с демонстрационным сохранением. Доступные названия и значки зависят от игровых файлов пользователя.

---

## Русский

**Cold Steel III Inventory Editor** позволяет просматривать инвентарь и изменять количество предметов в файлах сохранений Windows-версии _Trails of Cold Steel III_. Программа поддерживает русский и английский интерфейс, а также тёмную и светлую темы.

### Возможности

- Добавление и удаление предметов, изменение количества **от 1 до 99**.
- **Массовое добавление:** выбери несколько строк через **Ctrl** или **Shift**, укажи количество и примени его ко всем выбранным предметам.
- Поиск по названию и ID, сортировка столбцов, категории предметов: оружие, броня, кварцы, рецепты и другие.
- Автоматический поиск последнего совместимого сохранения `saveXXX.dat` и ручное открытие файла.
- Сохранение изменённой копии или перезапись с резервным копированием, а также отмена правок.
- Автоматическое сканирование игровых таблиц `.tbl`, включая поддерживаемые DLC.
- Значки предметов с кешированием; если оригинальная иконка недоступна, используется запасной значок категории.
- Переключение **Русский / English** и **тёмная / светлая тема** без перезапуска.

### Установка и запуск

**Готовый EXE (рекомендуется):** открой раздел **Releases** справа на странице репозитория, скачай архив с Windows-версией, распакуй и запусти `CS3_Inventory_Editor.exe` (название может отличаться в зависимости от сборки). Устанавливать Python для такого EXE не нужно.

**Запуск из исходников:** установи [Python 3.10+](https://www.python.org/downloads/), скачай исходный код, распакуй его и запусти `Запустить.bat` либо команду `python app.py`.

### Как пользоваться

1. **Закрой игру** и сделай резервную копию исходного сохранения.
2. Запусти редактор: он попробует найти игру, игровые таблицы и последнее сохранение. При необходимости выбери их вручную.
3. Выбери категорию, найди один или несколько предметов и укажи количество.
4. Нажми **«Добавить / применить количество»** или **«Добавить выбранные предметы»**.
5. Сначала используй **«Сохранить копию…»**, а затем проверь результат в игре.

**Горячие клавиши:** `Ctrl+O` — открыть сохранение, `Ctrl+F` — поиск, `F5` — последнее сохранение, `Ctrl+S` — сохранить копию.

### Язык предметов и DLC

Интерфейс программы переведён на русский и английский. **Тексты самих игровых предметов не включены в публичный репозиторий**: редактор читает названия и описания из таблиц установленной игры. Для русских названий при английской установке нужна собственная русская таблица предметов или отдельно установленный пользовательский языковой пакет. Если перевода нет, программа обозначает отсутствующий язык вместо выдуманного перевода.

### Безопасность

> **Важно:** редактор предназначен для сохранений совместимой PC-версии _Cold Steel III_. Всегда сохраняй оригинальные файлы. Изменённые сохранения проверялись автоматическими тестами, но совместимость с любым состоянием игры не гарантируется. Изменение некоторых сюжетных предметов может повлиять на прохождение.

---

## English

**Cold Steel III Inventory Editor** is an unofficial Windows desktop tool for browsing and editing item quantities in _Trails of Cold Steel III_ save files. It offers Russian/English interface languages and light/dark themes.

### Features

- Add or remove items and set item quantities **from 1 to 99**.
- **Batch editing:** use **Ctrl** or **Shift** to select multiple items and apply one quantity in a single operation.
- Search by item name or ID, sort columns, and browse categories such as weapons, armor, quartz, recipes and more.
- Detect the newest compatible `saveXXX.dat` automatically or select a save manually.
- Save an edited copy, overwrite with backup, and undo changes.
- Scan installed `.tbl` item data, including supported DLC tables.
- Cache original item icons and fall back to category icons when artwork is unavailable.
- Switch between **Russian / English** and **dark / light** themes without restarting.

### Installation

**Windows EXE (recommended):** use the repository's **Releases** section, download the Windows build, extract it, and launch `CS3_Inventory_Editor.exe` (the filename may vary by build). Python is not required for the standalone EXE.

**From source:** install [Python 3.10+](https://www.python.org/downloads/), download the source code, extract it, and run `Запустить.bat` or `python app.py`.

### How to use

1. **Close the game** and back up your original save file.
2. Open the editor. It will attempt to locate the game tables and latest save; you can select either manually.
3. Browse a category, find one or more items, and enter the desired quantity.
4. Click **Add / update quantity** or **Add selected items**.
5. Choose **Save a copy** first and test the edited save in game.

**Shortcuts:** `Ctrl+O` open a save · `Ctrl+F` search · `F5` latest save · `Ctrl+S` save a copy.

### Item names, descriptions and localization

The **application UI** supports Russian and English. The public repository intentionally **does not contain game item databases or translated game text**. Item names and descriptions are loaded from the user's own installed game tables. Russian item text on an English installation requires a separately obtained Russian-localized table or a user-provided language pack. Missing translations are labelled rather than invented.

### Save safety

> **Important:** Only compatible _Cold Steel III_ PC save files are supported. Keep backups of your originals. Edited saves have been tested offline, but compatibility with every game state is not guaranteed. Modifying progression-related items may have unintended effects.

---

## For developers / Для разработчиков

Install development dependencies and run tests:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The repository also includes GitHub Actions workflows for automated tests and Windows EXE builds. See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md) and [SECURITY.md](SECURITY.md).

## License, attribution & disclaimer / Лицензия и отказ от ответственности

The editor's original source code is released under the [MIT License](LICENSE). This **does not** grant rights to the game, its artwork, texts, translations or trademarks. The public source release excludes proprietary game tables, original icon files and users' saves. Screenshot examples are provided to illustrate the application UI.

Исходный код редактора распространяется по [лицензии MIT](LICENSE). Лицензия **не распространяется** на игру, игровые изображения, тексты, переводы и товарные знаки. В публичный репозиторий не входят игровые таблицы, оригинальные PNG-иконки и пользовательские сохранения.

**Not affiliated with or endorsed by Nihon Falcom or NIS America.**  
**Проект не связан с Nihon Falcom или NIS America и не поддерживается ими официально.**
