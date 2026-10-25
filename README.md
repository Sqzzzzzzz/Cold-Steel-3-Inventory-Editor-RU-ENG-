# Cold Steel III Inventory Editor

Unofficial desktop inventory save editor for **The Legend of Heroes: Trails of Cold Steel III** (Windows/NISA save format). The UI supports Russian and English.

> **Before use:** Back up your saves and close the game. Edited saves have been regression-tested offline, but loading every possible edited save in the game has not been independently verified.

## Features

- Add, remove and change the quantity of items (1–99) by item ID.
- Select multiple items with **Ctrl**/**Shift** to set their quantities in one atomic operation with a single Undo.
- Browse categories, sort by clicking table headers and search by item name/ID.
- Auto-detect the newest compatible `saveXXX.dat` file or open one manually.
- Save a separate edited copy or overwrite with a backup.
- Import official item names/descriptions from the game's `.tbl` files (including supported DLC).
- Russian/English UI, light/dark themes and cached, original icon support.

## Windows installation

1. Install **Python 3.10 or later** from [python.org](https://www.python.org/downloads/).
2. Download this source release, extract it to a normal folder.
3. Run `Запустить.bat`, or run `python app.py` in the extracted folder.
4. Point the app to your legally installed Cold Steel III game folder if discovery fails.
5. Open a save, make edits, then start with **Save a copy**.

For optional better icon format handling, install `python -m pip install -r requirements.txt`. Internet is required only for downloading missing icon art. If an icon cannot be fetched, a generic category icon is shown.

## Localization

The application's **interface** is available in Russian and English. Item names and descriptions are not machine-translated. The original English game installation provides English item text; a Russian-localized game installation or a user-imported Russian item table supplies Russian item text. Missing language data is marked instead of fabricated.

## Develop and test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

On Linux (GUI tests need a virtual display):

```bash
sudo apt-get install xvfb python3-tk
xvfb-run -a python -m pytest -q
```

## Windows EXE

Run `Собрать_EXE.bat` with Python and PyInstaller installed. The application EXE does not bundle a Windows installation of the game or any copyrighted game item tables. Use the GitHub Actions Windows build workflow when developing on non-Windows platforms.

## Copyright and scope

This project is not affiliated with, sponsored by or endorsed by **Nihon Falcom**, **NIS America** or Valve. The included MIT license applies to this application's original code, not to the original game, third-party trademarks, artwork, localizations or assets. Game-derived item tables, original images and user saves are intentionally **not** included in the public source release.

To audit a previously cached game icon set without changing files, use `python audit_assets.py --catalog catalog_builtin.json --cache PATH_TO_CACHE`. In source-only releases, pass a catalog imported from your game. This audit checks file presence/format and mapping; it cannot certify the icon content against every in-game screen.

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and [CHANGELOG.md](CHANGELOG.md).
