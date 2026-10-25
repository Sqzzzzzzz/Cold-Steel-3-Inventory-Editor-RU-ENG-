"""Cold Steel III item families inferred from the category u16 in each TBL record.

The low byte represents an item family; a few values require the full u16.
Unknown codes deliberately remain under 'Прочее' instead of guessing from a name.
"""
from __future__ import annotations
from collections import OrderedDict

# Ordered display groups and subcategories. Entries are stable internal identifiers.
GROUPS = OrderedDict([
    ('quartz', ('Кварцы', [('quartz_normal','Обычные кварцы'),('quartz_master','Мастер-кварцы')])),
    ('equipment', ('Снаряжение', [('weapon','Оружие'),('armor','Броня'),('shoes','Обувь'),('accessory','Аксессуары')])),
    ('consumables', ('Расходники и еда', [('consumable','Лечение и бой'),('food','Готовые блюда'),('ingredient','Ингредиенты')])),
    ('library', ('Книги и рецепты', [('recipe','Рецепты'),('book','Книги и журналы')])),
    ('cosmetics', ('Внешний вид', [('costume','Костюмы'),('face','Аксессуары образа'),('hair','Причёски'),('decoration','Декор и раскраски')])),
    ('fishing', ('Рыбалка', [('fish','Рыба'),('fishing_gear','Удочки и снасти')])),
    ('special', ('Другие предметы', [('quest','Сюжетные и ключевые'),('material','Материалы и сепит'),('card','Карты и мини-игры'),('orbment','Сферы и улучшения'),('other','Прочее')])),
])

CATEGORY_TO_GROUP = {
    cat: group for group, (_, subcategories) in GROUPS.items()
    for cat, _ in subcategories
}
CATEGORY_NAMES = {
    cat: label for _, (_, subcategories) in GROUPS.items()
    for cat, label in subcategories
}

TYPE_CODE_TO_CATEGORY = {
    0x80:'material', 0x81:'consumable', 0x82:'quest', 0x84:'book',
    0x85:'recipe', 0x86:'card', 0x8c:'weapon', 0xbe:'armor',
    0xbf:'shoes', 0xc0:'accessory', 0xc1:'costume', 0xc2:'face',
    0xc3:'hair', 0xc5:'orbment', 0xc6:'decoration', 0xc7:'decoration',
    0xc8:'quartz_normal', 0xc9:'quartz_master',
    0xd2:'ingredient', 0xd3:'food', 0xd4:'food', 0xd5:'food',
    0xd6:'food', 0xd7:'food', 0xdc:'fish', 0xdd:'fishing_gear',
    0xde:'fishing_gear', 0xdf:'quest', 0xe6:'consumable',
}


def classify_record(kind: str, type_code: int) -> str:
    """Read native TBL category code (NOT the item ID or translated name)."""
    if kind == 'item_q':
        return 'quartz_normal'
    if type_code in (0x0382,):
        return 'material'
    return TYPE_CODE_TO_CATEGORY.get(type_code & 0xff, 'other')


def category_of(item: dict) -> str:
    category = item.get('category')
    if category in CATEGORY_TO_GROUP:
        return category
    return 'quartz_normal' if item.get('kind') == 'quartz' else 'other'


def item_in_category(item: dict, filter_id: str) -> bool:
    if filter_id == 'all':
        return True
    category = category_of(item)
    return (category == filter_id or CATEGORY_TO_GROUP[category] == filter_id)
