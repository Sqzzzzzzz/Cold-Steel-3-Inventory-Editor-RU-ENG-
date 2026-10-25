from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_icons import icon_key, EXACT_ITEM_ICON_FILES

try:
    from catalog_core import load_catalog_json
except Exception:  # GitHub source edition may not have a built-in catalog
    load_catalog_json = None


def test_u_material_override_table():
    assert EXACT_ITEM_ICON_FILES[60] == "U-Material (Sen III Item).png"


def test_u_material_key_when_catalog_available():
    if load_catalog_json is None or not (ROOT / "catalog_builtin.json").exists():
        return
    catalog = load_catalog_json(ROOT / "catalog_builtin.json")
    item = catalog[60]
    assert icon_key(item, 60) == "material_u"
