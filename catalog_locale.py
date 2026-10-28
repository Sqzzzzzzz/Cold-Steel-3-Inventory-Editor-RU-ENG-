"""Conservative locale checks; Latin letters alone do not establish English."""
import re

CYRILLIC=re.compile(r'[А-Яа-яЁё]')
EN_ANCHORS={0:'Tear Balm',1:'Teara Balm',5:'EP Charge I',60:'U-Material',
            220:'Fishing Bait',2250:'Sports Compendium',3300:'Needle Shoot'}


def catalog_locale(catalog):
    texts=[' '.join((str(r.get('name','')),str(r.get('description',''))))
           for r in catalog.values()]
    text=' '.join(texts)
    if CYRILLIC.search(text):return 'ru'
    # Accented French grammar must not be accepted as an English cache.
    if re.search(r'\b(?:les|des|une|aux|avec|soins|restaure|dégâts|équipé)\b',text,re.I):return 'fr'
    if any(catalog.get(i,{}).get('name')==name for i,name in EN_ANCHORS.items()):return 'en'
    if re.search(r'\b(?:the|with|restores|increases|reduces|English|equipped|allows)\b',text,re.I):return 'en'
    return 'unknown'


def english_catalog(catalog):
    return bool(catalog) and catalog_locale(catalog)=='en'
