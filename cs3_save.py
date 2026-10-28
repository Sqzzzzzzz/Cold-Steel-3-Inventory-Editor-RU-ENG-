"""Offline inventory editing for Trails of Cold Steel III (NISA Windows saves).

Layout was reverse-engineered by comparing two same-sized user-provided save
files (save016.dat and save017.dat). No external libraries are required.

WARNING: never edit a loaded save while the game is running; game load acceptance
has not yet been independently verified. Always maintain an untouched backup.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from dataclasses import dataclass
from catalog_visibility import NON_INVENTORY_ITEM_IDS

SAVE_SIZE = 0x1402C0  # 1,311,424 bytes
TABLE_OFFSET = 0x365A0
RECORD_SIZE = 32
RECORD_COUNT = 6144
TABLE_END = TABLE_OFFSET + RECORD_SIZE * RECORD_COUNT  # 0x665A0
EMPTY_ID = 9999
MAX_QUANTITY = 99  # seen in provided save files; conservative game UI stack cap
MAX_ITEM_ID = 65535


class SaveFormatError(ValueError):
    """A save doesn't match the measured Cold Steel III inventory layout."""


@dataclass(frozen=True)
class Item:
    slot: int
    item_id: int
    quantity: int


class CS3Save:
    def __init__(self, data: bytes):
        if not isinstance(data, bytes):
            raise TypeError('Expected raw .dat bytes')
        self._validate_header(data)
        self._original = data
        self._data = bytearray(data)
        self._validate_table(self._data)

    @classmethod
    def from_file(cls, path: str | Path) -> 'CS3Save':
        path=Path(path);before=path.stat()
        if before.st_size!=SAVE_SIZE:raise cls._size_error(before.st_size)
        with path.open('rb') as stream:data=stream.read(SAVE_SIZE+1)
        after=path.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise SaveFormatError('Файл изменился во время чтения; повторите открытие')
        return cls(data)

    @staticmethod
    def _size_error(size):
        return SaveFormatError(f'Размер {size} байт вместо ожидаемых {SAVE_SIZE}. '
                               'Редактор поддерживает проверенный тип сохранений CS3 NISA для Windows.')

    @staticmethod
    def _validate_header(data: bytes) -> None:
        if len(data) != SAVE_SIZE:
            raise CS3Save._size_error(len(data))
        if data[:8] != bytes.fromhex('02 00 00 00 01 00 00 00'):
            raise SaveFormatError('Неизвестная версия или тип файла сохранения')
        if int.from_bytes(data[8:12], 'little') != len(data):
            raise SaveFormatError('Длина в заголовке не совпадает с длиной файла')
        if TABLE_END > len(data):
            raise SaveFormatError('Таблица предметов выходит за конец сохранения')

    @staticmethod
    def _validate_table(data: bytes | bytearray) -> None:
        seen = set()
        empty_started = False
        empty_count = 0
        for slot in range(RECORD_COUNT):
            p = TABLE_OFFSET + slot * RECORD_SIZE
            rec = data[p:p + RECORD_SIZE]
            item_id = int.from_bytes(rec[:2], 'little')
            qty = int.from_bytes(rec[2:4], 'little')
            if rec[4:] != bytes(28):
                raise SaveFormatError(f'Неизвестные данные в записи инвентаря №{slot}; запись отменена')
            if item_id == EMPTY_ID:
                if qty != 0:
                    raise SaveFormatError(f'Слот №{slot} помечен пустым, но содержит количество {qty}')
                empty_started = True
                empty_count += 1
                continue
            if empty_started:
                raise SaveFormatError('Обнаружены предметы после пустых слотов — неизвестная структура инвентаря')
            if not 1 <= qty <= MAX_QUANTITY:
                raise SaveFormatError(f'Недопустимое количество {qty} для ID {item_id}, слот {slot}')
            if item_id in seen:
                raise SaveFormatError(f'Дублирующийся ID {item_id} — редактор остановлен')
            seen.add(item_id)
        if empty_count < 16:
            raise SaveFormatError('Не найдена достаточная область свободных слотов инвентаря')

    def items(self) -> list[Item]:
        result = []
        for slot in range(RECORD_COUNT):
            pos = TABLE_OFFSET + slot * RECORD_SIZE
            item_id = int.from_bytes(self._data[pos:pos+2], 'little')
            if item_id == EMPTY_ID:
                break
            qty = int.from_bytes(self._data[pos+2:pos+4], 'little')
            result.append(Item(slot, item_id, qty))
        return result

    def get_quantity(self, item_id: int) -> int:
        return next((item.quantity for item in self.items() if item.item_id == item_id), 0)

    @property
    def occupied_count(self) -> int:
        return len(self.items())

    @property
    def changed(self) -> bool:
        return self._original != self._data

    @property
    def original_sha256(self) -> str:
        return hashlib.sha256(self._original).hexdigest()

    @property
    def changed_bytes(self) -> int:
        return sum(a != b for a, b in zip(self._original, self._data))

    def reset(self):
        self._data = bytearray(self._original)

    def _write_record(self, slot: int, item_id: int, qty: int) -> None:
        pos = TABLE_OFFSET + slot * RECORD_SIZE
        self._data[pos:pos+RECORD_SIZE] = (
            item_id.to_bytes(2, 'little') + qty.to_bytes(2, 'little') + bytes(28))

    def set_quantity(self, item_id: int, qty: int):
        # Use the same transactional validator for single and batch edits.
        # In particular, Python booleans must never become item IDs/quantities.
        if type(item_id) is not int:
            raise ValueError('ID предмета должен быть числом от 0 до 65535, кроме 9999')
        self.set_quantities({item_id: qty})

    def set_quantities(self, changes: dict[int, int]) -> None:
        """Apply many inventory edits in one verified, atomic operation.

        Existing item order is retained; new items are appended in caller order.
        Zero removes an item. On invalid input or insufficient capacity, the
        in-memory save remains byte-for-byte unchanged.
        """
        if not isinstance(changes, dict):
            raise TypeError('Expected an ID-to-quantity mapping')
        if not changes:
            return
        for item_id, qty in changes.items():
            if type(item_id) is not int or not 0 <= item_id <= MAX_ITEM_ID or item_id == EMPTY_ID:
                raise ValueError('ID предмета должен быть числом от 0 до 65535, кроме 9999')
            if type(qty) is not int or not 0 <= qty <= MAX_QUANTITY:
                raise ValueError(f'Количество должно быть в диапазоне 0–{MAX_QUANTITY}')
            if item_id in NON_INVENTORY_ITEM_IDS and qty > 0:
                raise ValueError('ID 249 нельзя добавлять в обычный инвентарь; существующую запись можно удалить количеством 0')
        old = self.items()
        old_ids = {entry.item_id for entry in old}
        kept = [(entry.item_id, changes.get(entry.item_id, entry.quantity))
                for entry in old if changes.get(entry.item_id, entry.quantity) > 0]
        kept.extend((item_id, qty) for item_id, qty in changes.items()
                    if item_id not in old_ids and qty > 0)
        if len(kept) > RECORD_COUNT - 16:
            raise ValueError('Недостаточно свободных слотов для добавления')
        if len(kept) == len(old) and all(
                (entry.item_id, entry.quantity) == kept[i]
                for i, entry in enumerate(old)):
            return
        candidate = bytearray(self._data)
        for slot, (item_id, qty) in enumerate(kept):
            pos = TABLE_OFFSET + slot * RECORD_SIZE
            candidate[pos:pos + RECORD_SIZE] = (
                item_id.to_bytes(2, 'little') + qty.to_bytes(2, 'little') + bytes(28))
        for slot in range(len(kept), len(old)):
            pos = TABLE_OFFSET + slot * RECORD_SIZE
            candidate[pos:pos + RECORD_SIZE] = (
                EMPTY_ID.to_bytes(2, 'little') + bytes(RECORD_SIZE - 2))
        self._validate_table(candidate)
        self._data = candidate

    def bytes(self) -> bytes:
        self._validate_header(self._data)
        self._validate_table(self._data)
        return bytes(self._data)


def read_catalog(path: str | Path) -> dict[int, str]:
    """Compatibility API: returns item names from a verified TBL or CSV parser."""
    from catalog_core import load_external_catalog
    return {item_id: item['name'] for item_id, item in load_external_catalog(path).items()}


def get_diff_summary(a: bytes, b: bytes) -> dict[str, object]:
    x = CS3Save(a)
    y = CS3Save(b)
    amap = {entry.item_id: entry.quantity for entry in x.items()}
    bmap = {entry.item_id: entry.quantity for entry in y.items()}
    return {
        'added': [(i, bmap[i]) for i in sorted(bmap.keys() - amap.keys())],
        'removed': [(i, amap[i]) for i in sorted(amap.keys() - bmap.keys())],
        'modified': [(i, amap[i], bmap[i]) for i in sorted(amap.keys() & bmap.keys()) if amap[i] != bmap[i]],
        'other_changed_bytes': sum(a[i] != b[i] for i in range(len(a)) if not TABLE_OFFSET <= i < TABLE_END),
    }
