# v7.9.6 — Safe CSV export and stable Russian catalog

- CSV export now uses an atomic write and rejects the opened save, its aliases and non-CSV paths. A missing extension is added automatically; UTF-8 names and unapplied inventory edits are retained.
- An English rescan preserves Russian entries whose names contain no Cyrillic characters, including EP 1, along with their descriptions and locale after restarting. Fresh English text is still available in English mode.
- Added 18 regression cases for the two issues confirmed by an independent review. The packaged self-test also checks CSV export and source-save protection.
- Includes the Python 3.10 Qt stability, locale-marker and category-count fixes from v7.9.5.

# v7.9.5 — Python 3.10 stability and locale markers

- Reproduced the CI abort on CPython 3.10.22: PySide6/Shiboken 6.12.0 decrements None references on repeated void painting calls. Constrained Qt to the verified <6.12 range; Python 3.10 remains in CI.
- Added an isolated 10,000-redraw regression check and enabled detailed CI crash traces.
- Russian item names shared with English (for example EP 1) now respect the original catalog locale. Old Russian caches without per-record locale are recognized once during catalog rebuild; explicit English entries keep their marker.
- Category counts now occupy a content-sized column in both catalog and inventory, preserving fixed panel widths.
- Local Windows packaging includes the same original-icon paths as the GitHub build.

# v7.9.4 — Qt release

- Default launch and Windows build now use qt_window.py; legacy Tk remains available.
- Fixed redirected Windows Saved Games lookup using the documented folder GUID.
- Search now includes the description shown in the card, including native generated quartz help.
- Scanning refreshes the selected card while preserving its unapplied quantity.
- Windows packaging tests both UI languages and save operations inside the actual EXE; release ZIP and SHA-256 checksum are produced together.

# v7.9.3 — Native data audit

- Исправлены ошибки выделения, неприменённого количества, групповых действий, импорта и записи файлов; уточнены английские подписи и ошибки.
- 80 изображений заменены прямыми фрагментами переданных игровых атласов. Привязки капли, приманки сияющей пом и общего значка всех 25 видов рыбы подтверждены владельцем.
- Неподдерживаемый ID 249 исключён из добавления; имеющуюся запись можно явно удалить с возможностью отмены.
- Импорт английской базовой таблицы сохраняет ранее загруженные DLC и неприменённое количество.
- Недостающие английские описания Needle Shoot, Waterfall, Strike 1–3 и Revolution восстанавливаются из родных таблиц магии и помощи; данные сохраняются после перезапуска.
- 141 тест пройден, 26 проверок старого Tk-интерфейса пропущены без дисплея. Windows EXE и загрузка сохранений самой игрой в этом проходе не проверены.

# v7.9.2 — First launch

- Добавлена панель первого запуска: загрузка каталога и открытие сохранения.
- Поиск игры, чтение таблиц и подготовка каталога отображаются отдельными этапами с индикатором выполнения.
- Кнопки указывают следующий доступный шаг; действия сохранения недоступны до открытия файла.
- Ошибки поиска и чтения отображаются в панели. Существующий каталог не теряется при неудачном повторном сканировании.
- После выбора файла из панели открывается инвентарь. Панель можно пропустить или снова открыть через «Инструменты» → «Начало работы».
- Исправлена диагностика отсутствующих иконок: учитывается встроенный набор оригинальных игровых изображений.
- Проверены компактная компоновка и масштабирование Qt 100%, 125%, 150%.
- Добавлены проверки реального рабочего потока сканирования и снимки всех состояний первого запуска.

# v7.9.1 — Review and original game icons

- Добавлены отметки изменённых строк и сравнение количества в карточке.
- Добавлено окно проверки правок перед записью; отмена просмотра не меняет сохранение.
- Быстрый фильтр избранного расположен рядом с поиском.
- Карточка показывает категорию и основной источник / DLC; длинные названия адаптируются к доступному месту.
- Сохранение, отмена, применение правок и избранное подтверждаются уведомлениями внутри окна.
- Включены 115 оригинальных игровых изображений; собственные медальоны и сгенерированные изображения предметов убраны.
- Проверены компактная компоновка и реальный Qt-рендер при 100%, 125% и 150%.
- Фиксированная ширина панелей сохранена. Ядро сохранений не менялось.

# v7.9.0 — Reference HUD

- Полностью перестроен Qt-интерфейс по образцу: расположение панелей, верхние действия, вкладки, рамки, таблица и карточка предмета.
- Новый оригинальный фон академии; векторные кнопки, пиктограммы и медальоны для отсутствующих иконок.
- Панель категорий теперь есть в каталоге и в инвентаре; их фильтры независимы.
- Групповые действия появляются при выделении нескольких строк. Редкие фильтры и быстрые количества сохранены в меню.
- Собственные оконные кнопки, перемещение заголовком, разворачивание и угол изменения размера.
- Отдельная демонстрация с синтетическими данными без записи пользовательского профиля.
- Скрипты запуска ведут к новой Qt-версии; исправлены размеры и границы панелей в компактном окне.
- Формат сохранения, проверка записи, резервные копии и ядро редактора не менялись.

## v7.8.5 Qt HUD BETA

- Replaced the blurred HUD background with a new original academy/city backdrop better matched to the Cold Steel III-inspired interface style.
- Preserved safe contrast so HUD panels and text remain readable in both large and compact window sizes.
- No changes to save parsing or writing logic.

## v7.8.1 — Qt HUD refinement (test build)
- Added subtle procedural hexagon grid to the right-hand backdrop.
- Improved responsive catalog column widths at compact window sizes.
- Applied separate inventory table column widths.
- Kept the save engine unchanged and the single game theme.
- Windows EXE and in-game save loading still require Windows validation.

## v7.7.0 Qt HUD BETA (not published)

- Rebuilt the interactive game-inspired glass panels using Qt painter gradients and chamfered cyan edges.
- Reworked table selection highlights, category tree, typography, scrollbars, header and main buttons.
- Added compatible system icons for nav and save operations (instead of unsupported glyphs).
- Moved Favorites into a compact action at the top of the selected-item panel.
- Display actual owned quantity and default proposed quantity to 1 for missing items.
- Clear stale selected item detail when loading a new save.
- Preserve uncommitted quantity field when switching RU/EN languages.
- Use bundled feather icon for the Qt window when available.
- Separate theme stylesheet (`qt_hud_theme.py`) for easier future QA.
- Keep save editing engine and separate beta configuration unchanged.

## 7.5.0 GAME HUD BETA (test-only)
- Better steel-and-glass HUD; refined metallic arc, corners and selection visuals.
- Responsive right item panel and compact toolbar at 1350×770.
- Fix: catalog category no longer filters the unrelated inventory table.
- Improve RU/EN translations for new controls.
- New regression tests for compact UI and safe inventory browsing.

## 7.3.0 HUD BETA

- Closer Cold Steel III-inspired visual layout with original blurred academy backdrop, angled interactive tabs and glass header.
- Search, right-side item card and secondary controls refined.
- 45 regression tests passing.
- Experimental beta only; GitHub stable release is unchanged.

# Changelog

## 7.1.0 BETA — Game UI test build (not published)

- Replaced light/dark settings with one Cold Steel III-inspired cyan/steel theme.
- Added separate Inventory, Catalog and Tools screens with a fixed-width item card.
- Added favorites, recent additions, owned/missing and base/DLC filtering.
- Added atomic inventory multi-delete, add-one-each, and retained batch add/undo.
- Added CSV export, diagnostics, backup import and safer read-only icon reports.
- Added a separate beta user profile and one-time read-only import from stable profile.
- Added bilingual UI phrases and GUI regression tests.
- No changes to the save-file binary parser and write engine.
- Windows EXE still requires a local Windows PyInstaller build.

---

## v7.0.1 — Localization fallback fix

- Fixed false `[EN]` labels on Russian-language item entries whose names match English spelling (e.g., **HP 1**, **EP 1**).
- Added support for **user-installed, separately distributed Russian language packs** via `_locale: "ru"` metadata in `%APPDATA%/CS3InventoryEditor/catalog_overrides.json`.
- Detect source language of scanned tables once per reload rather than inspecting every row during rendering.
- No copyrighted item text, PNG or proprietary assets are included in public source.

# Changelog

## 7.0 — 2026-10-25

- Atomic bulk inventory updates: a group change now validates the save table once instead of repeatedly per item.
- Regression tests for rollback, preserving non-inventory data, larger batches and language UI.
- Corrected version label and late-added English translations; fixed the quantity-range error message.
- Rechecked original icon selection by ID and identified one missing cache asset (`Booster`) in the submitted user asset sample.
- Added release documentation and CI checks for the public source variant.
- Added an offline asset audit command for checking icon caches and explicit missing files.
- Removed silent Pillow installation from the normal Windows launcher; dependency installation is now opt-in.

## 6.5

- Exact U-Material icon for item ID 60.

## 6.4

- Included original English catalog in the private/offline owner edition; source releases load legally owned game tables at runtime.

## 6.3

- Added multi-select item editing and corrected specific Russian DLC strings.

## v7.6.0 Qt Preview — 2026-10-25

- Экспериментальная вторая оболочка на PySide6: стеклянные панели, угловые вкладки, бледная подложка городского пейзажа.
- Отдельный тестируемый контроллер с безопасным редактированием и резервным копированием.
- Независимый профиль БЕТА, RU/EN, сканирование игры в worker-потоке.
- Windows-скрипты для запуска/сборки Qt; Tk-версия остаётся как fallback.
- Qt runtime здесь не проверен: 59 pass, 3 GUI skipped.

## v7.8.0 Qt HUD BETA (testing, not released)

- Render aligned academy scenery behind interactive translucent Qt panels.
- Improve font sizing, table rows, master quartz detail card, custom vector nav/action icons.
- Use bundled category fallback PNGs if original game icons are unavailable.
- Adapt table widths and navigation to 1320–1650 px windows without reloading rows on resize.
- Fix favorite star updating and tooltip/word wrapping in tabular lists.
- Add real Qt rendering preview and five v7.8 GUI regression tests.
# v7.9.3 — diagnostics and data audit

- Fix selection by item ID after sorting/filtering, stale bulk controls and inspector selection across sections.
- Read inventory quantities once per catalog pass; remove repeated full inventory parsing.
- Publish save copies without replacing competing files; recheck the source before commit and clean up failed backup writes.
- Use transactional single edits, bounded save/table reads, validated catalog records and sanitized favorite IDs.
- Parse the common native ItemData prefix for quartz; expose native stats for placeholder descriptions.
- Correct 30 normal-tier quartz icons, use native food/cover types, verify original artwork hashes and remove unverified specific fallbacks.
- Audit English controls, menus, tooltips, errors, scan summaries and original item texts; add explicit English catalog import and conservative locale checks.
- Update GitHub Windows workflow to build and smoke-test the Qt application with its resources.
- Add reproducible owner-data audit, regression coverage and real-data screenshots. See DIAGNOSTICS_V793_RU.md for coverage and remaining unverified icons.
