# Cold Steel III Inventory Editor v7.9.7

The Windows release uses the new PySide6 game-style UI. Russian and English UI languages, original game icons, favorites, bulk edits and a review dialog are included.

Download the Windows ZIP from Releases, extract it and run `CS3_Inventory_Editor.exe`. Python is not needed for the EXE. From source, install Python 3.10+, run `python -m pip install -r requirements.txt`, then `python qt_window.py`. On Windows, `Запустить.bat` prepares a local environment and opens the Qt editor.

On first launch, scan your game installation and open a compatible `saveXXX.dat`. Use Save a copy first. Overwriting the original creates a backup. Only the verified CS3 NISA Windows save layout is supported; game-side loading for every possible item/state has not been verified.

Game tables, item databases and user saves are excluded from the public source. Item names/descriptions come from the user's game. Original icon PNGs are included and attributed in `icons/original/sources.json`; game artwork is owned by its respective rightsholders.

Use Tools → Import English catalog for original English text. Optional English `t_itemhelp.tbl` and `t_magic.tbl` beside the item table recover six missing quartz descriptions. Previously loaded DLC translations are retained. For further instructions, save folder paths and screenshots, see [README.md](README.md#english).

Build on Windows using `Собрать_EXE.bat`. The output is `dist/CS3_Inventory_Editor.exe` and a Windows ZIP in `release`. The legacy Tk interface is retained as `app.py`.
