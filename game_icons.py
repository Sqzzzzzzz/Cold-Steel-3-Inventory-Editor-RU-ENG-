"""Original item category icon artwork from the Cold Steel III Kiseki Wiki.

Only icon-type artwork is downloaded.  The editor never modifies game files.
All downloads occur on a worker thread in app.py.  No requests run on import.
Downloaded icons are cached in %APPDATA% and usable offline after download.

The small icons used by the game typically represent a *type* of item, rather
than a unique image for every inventory ID.  Where an exact match is unknown,
only a corresponding category picture is displayed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import json
import io
import re
import os
from pathlib import Path
import tempfile
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
from urllib.request import Request, urlopen
import zlib

from categories import category_of

# Confirmed game-artwork filenames, see Kiseki Wiki's CS3 icon file index.
GAME_ICON_FILES = {
    'weapon': 'Tachi (Sen III Weapon).png',
    'weapon_tachi': 'Tachi (Sen III Weapon).png',
    'weapon_gunbreakers': 'Gunbreakers (Sen III Weapon).png',
    'weapon_twin_swords_kurt': 'Twin Swords Kurt (Sen III Weapon).png',
    'weapon_claiomh_solais': 'Claiomh Solais (Sen III Weapon).png',
    'weapon_orbal_carbine': 'Orbal Carbine (Sen III Weapon).png',
    'weapon_axe': 'Axe (Sen III Weapon).png',
    'weapon_orbal_bow': 'Orbal Bow (Sen III Weapon).png',
    'weapon_orbal_staff_elliot': 'Orbal Staff Elliot (Sen III Weapon).png',
    'weapon_greatsword_laura': 'Greatsword Laura (Sen III Weapon).png',
    'weapon_orbal_shotgun': 'Orbal Shotgun (Sen III Weapon).png',
    'weapon_orbal_staff_emma': 'Orbal Staff Emma (Sen III Weapon).png',
    'weapon_sword_jusis': 'Sword Jusis (Sen III Weapon).png',
    'weapon_twin_gunswords': 'Twin Gunswords (Sen III Weapon).png',
    'weapon_spear': 'Spear (Sen III Weapon).png',
    'weapon_airgetlam': 'Airgetlam (Sen III Weapon).png',
    'weapon_sword_and_gun': 'Sword and Gun (Sen III Weapon).png',
    'weapon_orbal_gun_claire': 'Orbal Gun Claire (Sen III Weapon).png',
    'weapon_greatsword_agate': 'Greatsword Agate (Sen III Weapon).png',
    'weapon_orbal_staff_tio': 'Orbal Staff Tio (Sen III Weapon).png',
    'weapon_dagger': 'Dagger (Sen III Weapon).png',
    'weapon_orbal_gun_olivier': 'Orbal Gun Olivier (Sen III Weapon).png',
    'weapon_gauntlets_angelica': 'Gauntlets Angelica (Sen III Weapon).png',
    'weapon_arcadia': 'Arcadia (Sen III Weapon).png',
    'weapon_orbal_gear': 'Orbal Gear (Sen III Weapon).png',
    'weapon_rapier_lechter': 'Rapier Lechter (Sen III Weapon).png',
    'armor': 'Armour (Sen III Item).png',
    'shoes': 'Boots (Sen III Item).png',
    'accessory': 'Accessory (Sen III Item).png',
    'consumable': 'Potion (Sen III Item).png',
    'consumable_booster': 'Booster (Sen III Item).png',
    'food': 'Food Regular (Sen III Item).png',
    'food_superb': 'Food Superb (Sen III Item).png',
    'food_regular': 'Food Regular (Sen III Item).png',
    'food_peculiar': 'Food Peculiar (Sen III Item).png',
    'food_unique': 'Food Unique (Sen III Item).png',
    'food_attack': 'Food Attack (Sen III Item).png',
    'ingredient': 'Food Ingredient (Sen III Item).png',
    'recipe': 'Book (Sen III Item).png',
    'book': 'Book (Sen III Item).png',
    'costume': 'Cosmetic Armour (Sen III Item).png',
    'face': 'Cosmetic Accessory (Sen III Item).png',
    'hair': 'Cosmetic Hair (Sen III Item).png',
    'decoration': 'Cosmetic Armour (Sen III Item).png',
    'fish': 'Fish M (Sen III Item).png',
    'fish_s': 'Fish S (Sen III Item).png',
    'fish_m': 'Fish M (Sen III Item).png',
    'fish_l': 'Fish L (Sen III Item).png',
    'fishing_gear': 'Fishing Rod (Sen III Item).png',
    'quest': 'Key (Sen III Item).png',
    'material': 'Earth (Sen III Sepith).png',
    'material_sepith_earth': 'Earth (Sen III Sepith).png',
    'material_sepith_water': 'Water (Sen III Sepith).png',
    'material_sepith_fire': 'Fire (Sen III Sepith).png',
    'material_sepith_wind': 'Wind (Sen III Sepith).png',
    'material_sepith_time': 'Time (Sen III Sepith).png',
    'material_sepith_space': 'Space (Sen III Sepith).png',
    'material_sepith_mirage': 'Mirage (Sen III Sepith).png',
    'material_sepith_mass': 'Mass (Sen III Sepith).png',
    'material_u': 'U-Material (Sen III Item).png',
    'material_key': 'Key (Sen III Item).png',
    'fishing_bait': 'Key (Sen III Item).png',
    'orbment': 'Orbment (Sen III Item).png',
    'card': 'VM Card (Sen III Item).png', # Original Vantage Masters card icon
    'quartz_master': 'Master (Sen III Slot).png',
    'quartz_normal': 'Earth (Sen III Quartz).png',
    'other': 'DLC (Sen III Item).png',
}

WEAPON_ICON_RANGES = (
    (1200, 1210, 'weapon_tachi'),
    (1215, 1225, 'weapon_gunbreakers'),
    (1230, 1240, 'weapon_twin_swords_kurt'),
    (1245, 1254, 'weapon_claiomh_solais'),
    (1260, 1266, 'weapon_orbal_carbine'),
    (1275, 1280, 'weapon_axe'),
    (1290, 1292, 'weapon_orbal_bow'),
    (1300, 1302, 'weapon_orbal_staff_elliot'),
    (1310, 1312, 'weapon_greatsword_laura'),
    (1320, 1322, 'weapon_orbal_shotgun'),
    (1330, 1332, 'weapon_orbal_staff_emma'),
    (1340, 1342, 'weapon_sword_jusis'),
    (1350, 1352, 'weapon_twin_gunswords'),
    (1360, 1362, 'weapon_spear'),
    (1370, 1373, 'weapon_airgetlam'),
    (1380, 1382, 'weapon_sword_and_gun'),
    (1390, 1392, 'weapon_orbal_gun_claire'),
    (1400, 1401, 'weapon_greatsword_agate'),
    (1410, 1411, 'weapon_orbal_staff_tio'),
    (1420, 1421, 'weapon_dagger'),
    (1430, 1431, 'weapon_orbal_gun_olivier'),
    (1440, 1440, 'weapon_gauntlets_angelica'),
    (1450, 1450, 'weapon_arcadia'),
    (1460, 1460, 'weapon_orbal_gear'),
    (1470, 1470, 'weapon_rapier_lechter'),
)

# The item_q element is read directly from the game's binary table (element metadata after the quartz flags).
QUARTZ_ELEMENTS = {1:'Earth',2:'Water',3:'Fire',4:'Wind',5:'Time',6:'Space',7:'Mirage'}
for _element in QUARTZ_ELEMENTS.values():
    lower = _element.lower()
    GAME_ICON_FILES['quartz_'+lower] = f'{_element} (Sen III Quartz).png'
    GAME_ICON_FILES['quartz_'+lower+'_r'] = f'{_element} R (Sen III Quartz).png'
    GAME_ICON_FILES['quartz_'+lower+'_sr'] = f'{_element} SR (Sen III Quartz).png'

GAME_ICON_FILES['quartz_lost'] = 'Lost (Sen III Quartz).png'

# Individual Trails of Cold Steel III master-quartz emblems (wiki source names).
# EX variants explicitly reuse the base emblem, as they do in the game.
# Native IDs are independent of language/localized text and remain stable.
MASTER_QUARTZ_NAMES = {
    3200: 'Brigid', 3201: 'Skuld', 3202: 'Sirius', 3203: 'Deva',
    3204: 'Canon', 3205: 'Regulus', 3206: 'Zephyr', 3207: 'Kaleido',
    3208: 'Oberon', 3209: 'Moebius', 3210: 'Sophia', 3211: 'Keeper',
    3212: 'Titania', 3213: 'Gloom', 3214: 'Katze', 3215: 'Virgo',
    3216: 'Scorpio', 3217: 'Dynamis', 3218: 'Tempest', 3219: 'Aegis',
    3220: 'Thor', 3221: 'Beowulf', 3222: 'Minotauros', 3223: 'Pandora',
    3224: 'Emblem', 3225: 'Magius', 3226: 'Chevalier', 3227: 'Gungnir',
    3228: 'Regalia', 3229: 'Valhalla',
    3240: 'Kaleido', 3241: 'Moebius', 3242: 'Gloom', 3243: 'Katze',
    3244: 'Beowulf', 3245: 'Emblem', 3246: 'Chevalier', 3247: 'Aegis',
}
MASTER_QUARTZ_FILES = {item_id: f'{name} (Sen III MQ).png'
                       for item_id,name in MASTER_QUARTZ_NAMES.items()}
EXACT_ITEM_ICON_FILES = {
    # Exact item-specific overrides. These take precedence over category rules.
    60: 'U-Material (Sen III Item).png',
}
ALL_ORIGINAL_FILES = (set(GAME_ICON_FILES.values()) | set(MASTER_QUARTZ_FILES.values())
                      | set(EXACT_ITEM_ICON_FILES.values()))

# Exact official art titles from the Cold Steel III image and EX Orb indexes.
# Do not ship or derive any icon from cropped screenshots.
OFFICIAL_SPECIAL_ICONS = {
    'gift': 'Gift (Sen III Item).png',
    'sphere_hp': 'HP EX Orb (Sen III).png',
    'sphere_power': 'Power EX Orb (Sen III).png',
    'sphere_shield': 'Shield EX Orb (Sen III).png',
    'sphere_speed': 'Speed EX Orb (Sen III).png',
}


def special_local_icon_key(item_id: int, item: dict) -> str | None:
    """Return precise game-art family; never infer from broad category."""
    # The game's gift item table occupies one contiguous ID range.
    # Description checks permit international/custom catalogs without
    # accidentally identifying quest keys as presents.
    if 2250 <= item_id <= 2280 and category_of(item) == 'quest':
        # In the game's stock table, these 31 IDs are gifts. Do not use
        # localized wording so the English release gets identical icons.
        return 'gift'
    if 3150 <= item_id <= 3152:
        return 'sphere_hp'
    if 3153 <= item_id <= 3155:
        return 'sphere_power'
    if 3156 <= item_id <= 3158:
        return 'sphere_shield'
    if 3159 <= item_id <= 3161:
        return 'sphere_speed'
    return None


ALL_ORIGINAL_FILES.update(OFFICIAL_SPECIAL_ICONS.values())

FILE_PREFIX = 'File:'
API_URL = 'https://kiseki.fandom.com/api.php'
MAX_PNG_BYTES = 1_000_000  # max cached PNG
MAX_DOWNLOAD_BYTES = 8_000_000  # larger original MQ artwork is allowed
MAX_INPUT_DIMENSION = 4096
MAX_INPUT_PIXELS = 12_000_000
MAX_DIMENSION = 512
TARGET_ICON_DIMENSION = 96
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def icon_cache_dir(base: Path | None = None) -> Path:
    if base is not None:
        return Path(base)
    appdata = os.environ.get('APPDATA')
    return (Path(appdata) if appdata else Path.home()/'.config')/'CS3InventoryEditor'/'icons'/'original'


def _weapon_icon_key(item_id: int | None) -> str | None:
    if item_id is None:
        return None
    for start, end, key in WEAPON_ICON_RANGES:
        if start <= item_id <= end:
            return key
    return None


def _food_icon_key(item_id: int | None) -> str | None:
    if item_id is None:
        return None
    if 3000 <= item_id <= 3021:
        return 'food_superb'
    if 3022 <= item_id <= 3043:
        return 'food_regular'
    if 3044 <= item_id <= 3059:
        return 'food_peculiar'
    if 3060 <= item_id <= 3081:
        return 'food_unique'
    if 3090 <= item_id <= 3095:
        return 'food_attack'
    return None


def _fish_icon_key(item_id: int | None) -> str | None:
    if item_id is None:
        return None
    if 2100 <= item_id <= 2109:
        return 'fish_s'
    if 2110 <= item_id <= 2114:
        return 'fish_m'
    if 2115 <= item_id <= 2124:
        return 'fish_l'
    return None


def _material_icon_key(item_id: int | None, item: dict) -> str | None:
    if item_id == 60:
        return 'material_u'
    if item_id in (61,62):
        return 'material_key'
    sepith_by_id = {
        241: 'material_sepith_earth',
        242: 'material_sepith_water',
        243: 'material_sepith_fire',
        244: 'material_sepith_wind',
        245: 'material_sepith_time',
        246: 'material_sepith_space',
        247: 'material_sepith_mirage',
        248: 'material_sepith_mass',
        249: 'material_sepith_mass',
    }
    if item_id in sepith_by_id:
        return sepith_by_id[item_id]
    return None


# Physical ordering in the stock CS3 item_q table: normal, R, then SR.
# This is independent of translation and includes quartz without a rarity
# suffix (bells, gems, stat quartz, special effects).
QUARTZ_RARITY_ID_RANGES = (
    (3300, 3312, 'normal'), (3313, 3328, 'r'), (3329, 3346, 'sr'),
    (3347, 3361, 'normal'), (3362, 3379, 'r'), (3380, 3399, 'sr'),
    (3400, 3412, 'normal'), (3413, 3428, 'r'), (3429, 3446, 'sr'),
    (3447, 3458, 'normal'), (3459, 3473, 'r'), (3474, 3490, 'sr'),
    (3491, 3500, 'normal'), (3501, 3513, 'r'), (3514, 3528, 'sr'),
    (3529, 3538, 'normal'), (3539, 3551, 'r'), (3552, 3567, 'sr'),
    (3568, 3577, 'normal'), (3578, 3591, 'r'), (3592, 3606, 'sr'),
)


def quartz_rarity(item_id: int | None, item: dict) -> str:
    # Infer rarity using stock ID blocks; fallback to language-neutral tags.
    if isinstance(item_id,int):
        for lo,hi,rarity in QUARTZ_RARITY_ID_RANGES:
            if lo <= item_id <= hi:
                return rarity
    # Supplemental/modded quartz: use the game's encoded description marker
    # when present, then a multilingual name suffix (Latin R or Cyrillic Р).
    description = str(item.get('description',''))
    match = re.search(r'\((SR|R|UR)\)', description[:90], re.IGNORECASE)
    if match:
        return match.group(1).lower()
    name = str(item.get('name','')).rstrip().upper()
    if name.endswith((' SR',' ＳＲ')):
        return 'sr'
    if name.endswith((' R',' Р')):
        return 'r'
    return 'normal'


def icon_key(item: dict, item_id: int | None = None) -> str:
    item_id = item_id if item_id is not None else item.get('id')
    category = category_of(item)
    if category == 'consumable' and item_id in (50,51,52,53,54):
        return 'consumable_booster'
    if category == 'fishing_gear' and item_id == 220:
        return 'fishing_bait'
    if category == 'weapon':
        return _weapon_icon_key(item_id) or category
    if category == 'food':
        return _food_icon_key(item_id) or category
    if category == 'fish':
        return _fish_icon_key(item_id) or category
    if category == 'material':
        return _material_icon_key(item_id, item) or category
    if category == 'quartz_normal':
        element = str(item.get('element','')).lower()
        if element in (e.lower() for e in QUARTZ_ELEMENTS.values()):
            rarity = quartz_rarity(item_id, item)
            return 'quartz_' + element + ('_'+rarity if rarity != 'normal' else '')
    return category


def validate_png(data: bytes) -> bool:
    """Validate a bounded, standard PNG including chunk lengths and CRCs."""
    if len(data) < 45 or len(data) > MAX_PNG_BYTES or not data.startswith(PNG_MAGIC):
        return False
    pos = len(PNG_MAGIC)
    has_ihdr = False
    has_data = False
    while pos + 12 <= len(data):
        size = int.from_bytes(data[pos:pos+4], 'big')
        tag = data[pos+4:pos+8]
        end = pos + 12 + size
        if size > MAX_PNG_BYTES or end > len(data):
            return False
        body = data[pos+8:pos+8+size]
        expected = int.from_bytes(data[pos+8+size:end], 'big')
        if zlib.crc32(tag + body) & 0xffffffff != expected:
            return False
        if not has_ihdr:
            if tag != b'IHDR' or size != 13:
                return False
            w,h = int.from_bytes(body[:4],'big'), int.from_bytes(body[4:8],'big')
            if not (0 < w <= MAX_DIMENSION and 0 < h <= MAX_DIMENSION):
                return False
            has_ihdr = True
        if tag == b'IDAT':
            has_data = True
        if tag == b'IEND':
            return has_ihdr and has_data and size == 0 and end == len(data)
        pos = end
    return False


def _read_url(url: str, max_bytes: int = MAX_DOWNLOAD_BYTES, opener=None) -> bytes:
    opener = opener or urlopen
    request = Request(url, headers={'User-Agent':'CS3InventoryEditor/5.5 (personal local icon caching; info: Kiseki Wiki)', 'Accept':'image/png,application/json;q=0.9,*/*;q=0.2'})
    with opener(request, timeout=15) as response:
        payload = response.read(max_bytes+1)
    if len(payload)>max_bytes:
        raise ValueError('Слишком большой файл изображения')
    return payload


def _authorized_icon_url(url: str) -> bool:
    """MediaWiki API supplies download URLs; never follow arbitrary domains."""
    info=urlparse(url)
    host=(info.hostname or '').lower()
    return info.scheme == 'https' and (host=='static.wikia.nocookie.net' or host.endswith('.wikia.nocookie.net') or host=='kiseki.fandom.com')



def _original_png_url(url: str) -> str:
    """Request the uploaded PNG, not Fandom's auto-converted WebP preview.

    MediaWiki imageinfo.urls can contain /revision/latest and cache-busting
    parameters. Preserve them, but remove scaling and force format=original.
    Only URLs allowed by _authorized_icon_url may be used here.
    """
    if not _authorized_icon_url(url):
        raise ValueError('Недоверенный адрес изображения')
    parts = urlparse(url)
    path = re.sub(r'(/revision/latest)/scale-to-(?:width-down|height-down)/\d+.*$',r'\1',parts.path)
    query = [(k,v) for k,v in parse_qsl(parts.query,keep_blank_values=True)
             if k.lower() not in ('format','width','height')]
    query.append(('format','original'))
    return urlunparse(parts._replace(path=path,query=urlencode(query)))


def _describe_response(data: bytes) -> str:
    """Provide useful diagnostics without exposing response bodies or URLs."""
    if data.startswith(PNG_MAGIC):
        if len(data) >= 24 and data[12:16] == b'IHDR':
            w,h = int.from_bytes(data[16:20],'big'),int.from_bytes(data[20:24],'big')
            return f'PNG {w}×{h} пикселей, {len(data)} байт'
        return f'Повреждённый PNG, {len(data)} байт'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':return 'WebP'
    if data.startswith(b'\xff\xd8\xff'):return 'JPEG'
    if data.startswith((b'GIF89a',b'GIF87a')):return 'GIF'
    if data[:256].lstrip().lower().startswith((b'<!doctype html',b'<html',b'<?xml')) or b'<html' in data[:256].lower():
        return 'HTML (возможно ограничение доступа Fandom)'
    return 'неизвестные данные ('+str(len(data))+' байт; сигнатура '+data[:12].hex()+')'


def _ensure_png(data: bytes) -> bytes:
    """Normalize real wiki images into verified, compact PNGs for Tk.

    The original master quartz illustrations may be far larger than UI icons.
    Earlier releases incorrectly classified valid, large PNGs as unsupported.
    Pillow is used only for conversion/resizing; verified small PNGs work alone.
    """
    if validate_png(data):
        # A verified source PNG larger than the display icon is also resized,
        # avoiding 30 full-resolution PhotoImages on every UI refresh.
        width=int.from_bytes(data[16:20],'big')
        height=int.from_bytes(data[20:24],'big')
        if max(width,height) <= TARGET_ICON_DIMENSION:
            return data
        try:
            from PIL import Image
        except ImportError:
            return data  # still valid for Tk; optional optimization
    description = _describe_response(data)
    if description.startswith('HTML'):
        raise ValueError(f'Вместо изображения пришёл {description}')
    if not (data.startswith(PNG_MAGIC) or data.startswith(b'RIFF') and data[8:12]==b'WEBP'
            or data.startswith(b'\xff\xd8\xff') or data.startswith((b'GIF89a',b'GIF87a'))):
        raise ValueError(f'Ответ сервера не является изображением: {description}')
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise ValueError(f'{description}: для больших изображений и WebP необходим Pillow. '
                         'Установите: py -3 -m pip install Pillow') from exc
    try:
        with Image.open(io.BytesIO(data)) as img:
            w,h=img.size
            if not (0 < w <= MAX_INPUT_DIMENSION and 0 < h <= MAX_INPUT_DIMENSION
                    and w*h <= MAX_INPUT_PIXELS):
                raise ValueError(f'Необычный размер изображения: {w}×{h}')
            img.load()  # do not cache truncated/corrupt images
            rgba=img.convert('RGBA')
            rgba.thumbnail((TARGET_ICON_DIMENSION,TARGET_ICON_DIMENSION),Image.Resampling.LANCZOS)
            out=io.BytesIO()
            rgba.save(out,format='PNG',optimize=True)
            normalized=out.getvalue()
            if validate_png(normalized):
                return normalized
            raise ValueError('Преобразование привело к недопустимому PNG')
    except (OSError,UnidentifiedImageError) as exc:
        raise ValueError(f'Не удалось прочитать {description}: {exc}') from exc


def _thumbnail_png_url(url: str) -> str:
    """Preserve MediaWiki's explicit thumb dimensions; request native format."""
    if not _authorized_icon_url(url):
        raise ValueError('Недоверенный адрес миниатюры')
    parts = urlparse(url)
    query = [(k,v) for k,v in parse_qsl(parts.query,keep_blank_values=True)
             if k.lower() != 'format']
    query.append(('format','original'))
    return urlunparse(parts._replace(query=urlencode(query)))


def _lookup_images(files: dict[str,str], opener=None) -> dict[str,list[str]]:
    """Return fallback URLs for a small thumbnail AND a full original.

    Requesting a thumb from the MediaWiki API avoids transferring large MQ
    artwork and avoids requiring Pillow when Fandom provides a small PNG.
    """
    wanted = {str(name).replace('_',' ').casefold(): name for name in set(files.values())}
    names = sorted(set(files.values()))
    urls = {}
    for start in range(0, len(names), 20):
        titles = '|'.join(FILE_PREFIX+name for name in names[start:start+20])
        query=urlencode({'action':'query','prop':'imageinfo','iiprop':'url',
                         'iiurlwidth':TARGET_ICON_DIMENSION,
                         'titles':titles,'format':'json','formatversion':2})
        raw=_read_url(API_URL+'?'+query, 250_000, opener=opener)
        response=json.loads(raw.decode('utf-8'))
        if response.get('error'):
            raise ValueError(f"Ошибка MediaWiki API: {response['error']}")
        pages=response.get('query',{}).get('pages',[])
        for page in pages:
            normalized=str(page.get('title','')).removeprefix(FILE_PREFIX).replace('_',' ')
            filename=wanted.get(normalized.casefold())
            infos=page.get('imageinfo',[])
            if not infos or not filename:
                continue
            info=infos[0]
            candidates=[]
            thumbnail=info.get('thumburl','')
            full=info.get('url','')
            if isinstance(thumbnail,str) and _authorized_icon_url(thumbnail):
                candidates.append(_thumbnail_png_url(thumbnail))
            if isinstance(full,str) and _authorized_icon_url(full):
                candidates.append(_original_png_url(full))
            if candidates:
                urls[filename]=list(dict.fromkeys(candidates))
    return urls


def download_original_icons(folder: Path | None=None, opener=None, progress=None,
                            mapping: dict[str,str] | None=None) -> tuple[int,list[str]]:
    """Download/cache icons atomically. Successful cached PNGs are not downloaded twice.

    Returns (number of newly cached files, errors); never deletes previous icons.
    An injectable ``opener`` makes all remote behavior independently testable.
    """
    folder=icon_cache_dir(folder)
    entries=mapping if mapping is not None else {
        **GAME_ICON_FILES,
        **{f'master_{item_id}':name for item_id,name in MASTER_QUARTZ_FILES.items()},
        **{f'special_{name}':filename for name,filename in OFFICIAL_SPECIAL_ICONS.items()},
    }
    if not entries:
        return 0, []
    folder.mkdir(parents=True,exist_ok=True)
    # Reuse a single image for multiple categories sharing the same filename.
    unique_files = {name for name in entries.values()}
    present_files = {name for name in unique_files if validate_file(folder / _safe_filename(name))}
    to_find={name:name for name in unique_files - present_files}
    errors=[]
    added=0
    if to_find:
        try:
            urls=_lookup_images(to_find,opener=opener)
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
            return 0, [f'Не удалось получить список иконок: {exc}']
        def download_one(filename):
            candidates=urls.get(filename,[])
            if not candidates:
                return filename, 'Иконка не найдена в справочнике'
            failures=[]
            for url in candidates:
                try:
                    data=_read_url(url, opener=opener)
                    png=_ensure_png(data)
                    _atomic_write(folder/_safe_filename(filename),png)
                    return filename, None
                except (OSError,ValueError) as exc:
                    failures.append(str(exc))
            return filename, ' ; '.join(dict.fromkeys(failures))

        # A small bounded pool reduces startup time without flooding the wiki.
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs=[pool.submit(download_one,name) for name in sorted(to_find)]
            for future in as_completed(jobs):
                filename,error=future.result()
                if error is None:
                    added+=1
                    if progress: progress(added,len(to_find))
                else:
                    errors.append(f'{filename}: {error}')

    return added,errors


def _safe_filename(name: str) -> str:
    # Game icon titles are fixed here; reject pathological ones in all cases.
    if not name.lower().endswith('.png') or '/' in name or '\\' in name or '..' in name:
        raise ValueError('Недопустимое имя иконки')
    return name


def validate_file(path: Path) -> bool:
    try:
        if path.stat().st_size > MAX_PNG_BYTES:
            return False
        return validate_png(path.read_bytes())
    except OSError:
        return False


def _atomic_write(path: Path, data: bytes):
    fd,name=tempfile.mkstemp(prefix='.icon-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)


def import_original_icons(source_dir: Path, dest_dir: Path|None=None) -> tuple[int,list[str]]:
    """Import previously extracted original game PNGs without a network call.

    Recognizes category asset filenames from the wiki or numeric item ID
    filenames (e.g. `420.png`). Never overwrites a verified, cached image.
    Source directories are read-only; never modifies game installation.
    """
    source_dir=Path(source_dir)
    dest=icon_cache_dir(dest_dir)
    if not source_dir.is_dir():
        raise ValueError('Папка с иконками не найдена')
    dest.mkdir(parents=True,exist_ok=True)
    allowed=ALL_ORIGINAL_FILES
    count=0
    skipped=[]
    # Only one level deep plus by_id: avoid an accidental walk through 20GB game data.
    locations=list(source_dir.glob('*.png'))
    locations.extend((source_dir/'by_id').glob('*.png') if (source_dir/'by_id').is_dir() else [])
    if len(locations)>10000:
        raise ValueError('В папке слишком много изображений: выберите каталог с иконками')
    for file in locations:
        is_id=bool(re.fullmatch(r'\d{1,5}\.png',file.name))
        if not is_id and file.name not in allowed:
            continue
        try:
            png=_ensure_png(file.read_bytes())
        except (OSError,ValueError):
            skipped.append(file.name)
            continue
        target=(dest/'by_id'/file.name) if is_id else (dest/file.name)
        target.parent.mkdir(parents=True,exist_ok=True)
        if validate_file(target):
            continue
        _atomic_write(target,png)
        count+=1
    return count,skipped


def icon_file_for_item(item_id: int, item: dict, cache_dir: Path|None=None,
                       manual_dir: Path|None=None) -> Path|None:
    """Exact overrides > official special art > master quartz > category art.

    No unofficial screenshot crops are ever returned. The editor can operate
    offline, falling back to category artwork if the CDN is unavailable.
    """
    manual=Path(manual_dir) if manual_dir is not None else None
    if manual is not None:
        for loc in (manual/'by_id'/f'{item_id}.png',manual/f'{item_id}.png'):
            if validate_file(loc):
                return loc
    folder=icon_cache_dir(cache_dir)
    own_icon=folder/'by_id'/f'{item_id}.png'
    if validate_file(own_icon):
        return own_icon
    exact_name = EXACT_ITEM_ICON_FILES.get(item_id)
    if exact_name:
        exact_path = folder / _safe_filename(exact_name)
        if validate_file(exact_path):
            return exact_path
    special_key=special_local_icon_key(item_id,item)
    special_name=OFFICIAL_SPECIAL_ICONS.get(special_key)
    if special_name:
        official=folder / _safe_filename(special_name)
        if validate_file(official):
            return official
    master_name=MASTER_QUARTZ_FILES.get(item_id) if category_of(item)=='quartz_master' else None
    if master_name:
        original=folder/_safe_filename(master_name)
        if validate_file(original):
            return original
    names=[GAME_ICON_FILES.get(icon_key(item, item_id)),GAME_ICON_FILES.get(category_of(item))]
    for name in dict.fromkeys(n for n in names if n):
        orig=folder/_safe_filename(name)
        if validate_file(orig):
            return orig
    return None
