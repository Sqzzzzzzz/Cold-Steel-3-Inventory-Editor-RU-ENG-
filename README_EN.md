# Cold Steel III Inventory Editor v7.0 — GitHub Source Edition

Unofficial, bilingual desktop save inventory editor for *The Legend of Heroes: Trails of Cold Steel III*. Not affiliated with Nihon Falcom, NIS America or Steam.

## Run

Install Python 3.10+ and run `python app.py` (or `Запустить.bat` on Windows). Select the game directory if needed. The app reads the original item tables from `data/text/dat_en/t_item_en.tbl` and supported DLC `t_item.tbl` files in the legally installed game; it never edits those files.

No original game item names/descriptions, official art, translated catalogs or sample saves are distributed. The item catalog is initially empty until an installation is scanned. A clean English installation provides original English names and descriptions. Russian UI text is included, but Russian game-item text requires user-supplied Russian tables. Import additional tables via the Tools menu.

Features: category filtering, item search, edit quantity, add/remove multiple items with Ctrl/Shift selection and one-step undo, manual/automatic save opening, backup on overwrite, light/dark mode, game icon fetching/caching.

## Tests

Run `python -m pytest -q`. Tests use synthetic item tables, not any proprietary game content. On Linux, GUI tests require a display (e.g. `xvfb-run -a python -m pytest -q`). Modified saves were not exhaustively verified in-game.

See `README_GITHUB.md` for public distribution guidelines. The `LICENSE` applies to the application's code only.


## Version 7.0 review
Bulk modifications now use a single atomic inventory transaction. The English
version label, quantity validation message, icon audit tool and regression
coverage were updated. Original game artwork is not redistributed.
