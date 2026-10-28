# CS3 Inventory Editor v7.9.4

A new PySide6 game-style interface with Russian and English UI, original game icons, favorites, bulk editing and a review dialog before saving.

- Corrected item icon mappings, including all 25 fish and both Shining Pom items.
- Transactional edits, verified backups, no-overwrite save copies and external-change guards.
- Fixed Windows redirected Saved Games discovery, description search and stale item cards after scans.
- English imports retain DLC; six missing quartz descriptions are recovered from native magic/help tables.
- The default launcher and Windows build now start the Qt interface. Legacy Tk remains in the source.

Download the Windows ZIP, extract it and run `CS3_Inventory_Editor.exe`. Python is not required. On first launch, scan the game folder and select a compatible save. Game tables and user saves are not bundled. The included original icon artwork is attributed in the manifest.

The packaged Windows executable is checked for startup, both UI languages, all 115 PNG hashes, atomic edits, Unicode paths, undo, saving a copy and backup overwrite. Tests use disposable synthetic saves. Actual in-game loading across every possible game state is not claimed; start by saving a separate copy.

---

Новый игровой интерфейс на PySide6 с русским и английским языками, оригинальными иконками, избранным, массовыми правками и просмотром изменений перед записью.

Исправлены поиск перенесённой папки Saved Games в Windows, поиск по восстановленным описаниям, обновление карточки после сканирования, импорт английского каталога с сохранением DLC и привязки игровых значков. Восстановлены шесть английских описаний кварцев из игровых таблиц.

Скачайте Windows ZIP, распакуйте его и запустите `CS3_Inventory_Editor.exe`. Python не требуется. При первом запуске укажите папку игры и файл сохранения. Начинайте с «Сохранить копию…» и проверяйте результат в игре.
