"""Extract the *actual installed Tk* window icon into a Windows .ico.

This deliberately reads the icon resource from the Tk DLL packaged with the
Python interpreter used to build the application; no external icon service and
no recreations from screenshots. Requires ``pefile`` on the Windows builder.

Usage: python tools/extract_tk_icon.py icons/app_icon.ico
"""
from __future__ import annotations

import os
from pathlib import Path
import struct
import sys

RT_ICON = 3
RT_GROUP_ICON = 14


def candidate_tk_dlls() -> list[Path]:
    roots = [Path(sys.executable).parent, Path(sys.base_prefix), Path(sys.prefix)]
    try:
        import _tkinter
        roots.append(Path(_tkinter.__file__).parent)
    except ImportError:
        pass
    candidates = []
    for root in roots:
        for rel in ('tk86t.dll', 'DLLs/tk86t.dll', 'Library/bin/tk86t.dll',
                    'tk87t.dll', 'DLLs/tk87t.dll', 'Library/bin/tk87t.dll'):
            candidate = root / rel
            if candidate.is_file() and candidate not in candidates:
                candidates.append(candidate)
    return candidates


def resource_id_name(entry) -> str:
    if getattr(entry, 'name', None) is not None:
        raw = getattr(entry.name, 'string', b'')
        if isinstance(raw, bytes):
            try:
                return raw.decode('utf-8').rstrip('\x00').casefold()
            except UnicodeDecodeError:
                return raw.decode('utf-16-le', errors='replace').rstrip('\x00').casefold()
        return str(raw).casefold()
    return str(getattr(entry, 'id', ''))


def find_resources(pe, type_id: int) -> dict[str, bytes]:
    results: dict[str, bytes] = {}
    for typ in getattr(pe, 'DIRECTORY_ENTRY_RESOURCE', []).entries:
        if getattr(typ, 'id', None) != type_id:
            continue
        for ident in typ.directory.entries:
            for language in ident.directory.entries:
                data_entry = language.data.struct
                blob = pe.get_data(data_entry.OffsetToData, data_entry.Size)
                key = resource_id_name(ident)
                results.setdefault(key, blob)
    return results


def assemble_ico(group_blob: bytes, icon_blobs: dict[int, bytes]) -> bytes:
    """Build a self-contained ICO from RT_GROUP_ICON and RT_ICON resources."""
    if len(group_blob) < 6:
        raise ValueError('Tk group-icon resource is too short')
    reserved, kind, count = struct.unpack_from('<HHH', group_blob)
    if reserved != 0 or kind != 1 or not (1 <= count <= 64):
        raise ValueError(f'Invalid group icon header: {reserved}, {kind}, {count}')
    if len(group_blob) < 6 + count * 14:
        raise ValueError('Truncated Tk group icon directory')

    directory = bytearray(struct.pack('<HHH', 0, 1, count))
    image_data = bytearray()
    next_offset = 6 + count * 16
    for idx in range(count):
        width, height, colors, zero, planes, bits, length, image_id = struct.unpack_from(
            '<BBBBHHIH', group_blob, 6 + idx * 14
        )
        if image_id not in icon_blobs:
            raise ValueError(f'Missing Tk RT_ICON resource: {image_id}')
        data = icon_blobs[image_id]
        if not data:
            raise ValueError(f'Empty Tk icon resource: {image_id}')
        directory += struct.pack('<BBBBHHII', width, height, colors, zero,
                                 planes, bits, len(data), next_offset)
        image_data += data
        next_offset += len(data)
    return bytes(directory + image_data)


def extract_feather_icon(source: Path, destination: Path) -> int:
    import pefile  # installed on Windows GitHub runner
    pe = pefile.PE(str(source), fast_load=False)
    try:
        if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']]
            )
        groups = find_resources(pe, RT_GROUP_ICON)
        icons_by_name = find_resources(pe, RT_ICON)
        icon_blobs = {int(name): value for name, value in icons_by_name.items() if name.isdigit()}
        if not groups or not icon_blobs:
            raise ValueError(f'No icon resources found in {source}')
        if 'tk' in groups:
            group_blob = groups['tk']
            group_label = 'tk'
        elif len(groups) == 1:
            group_label, group_blob = next(iter(groups.items()))
            print(f'Note: Tk DLL has one icon group named {group_label!r}')
        else:
            raise ValueError(f'Tk icon group not uniquely identified: {sorted(groups)}')
        ico = assemble_ico(group_blob, icon_blobs)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(ico)
        print(f'Extracted {group_label!r} icon from {source} -> {destination} ({len(ico)} bytes)')
        return struct.unpack_from('<H', ico, 4)[0]
    finally:
        pe.close()


def ico_payloads(path: Path) -> list[bytes]:
    """Return the actual image bytes from every ICO frame for verification."""
    ico = path.read_bytes()
    if len(ico) < 6:
        raise ValueError('ICO header is truncated')
    reserved, icon_type, count = struct.unpack_from('<HHH', ico)
    if reserved != 0 or icon_type != 1 or count < 1 or len(ico) < 6 + 16 * count:
        raise ValueError('ICO directory is invalid')
    frames = []
    for i in range(count):
        _w, _h, _colors, _reserved, _planes, _bpp, length, offset = struct.unpack_from(
            '<BBBBHHII', ico, 6 + 16 * i
        )
        if not length or offset + length > len(ico):
            raise ValueError('Invalid ICO frame offset/length')
        frames.append(ico[offset:offset+length])
    return frames


def verify_exe_icon(exe_path: Path, expected_ico: Path) -> None:
    """Fail CI if the EXE embeds a different icon than the real Tk feather."""
    import pefile
    expected_frames = ico_payloads(expected_ico)
    pe = pefile.PE(str(exe_path), fast_load=False)
    try:
        if not hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']]
            )
        groups = find_resources(pe, RT_GROUP_ICON)
        icon_bytes = set(find_resources(pe, RT_ICON).values())
        if not groups or not icon_bytes:
            raise ValueError(f'No embedded Windows icon resources in {exe_path}')
        missing = [i for i, frame in enumerate(expected_frames) if frame not in icon_bytes]
        if missing:
            raise ValueError(f'EXE icon mismatch: {len(missing)} Tk image frame(s) missing')
        print(f'Verified genuine Tk feather in EXE: {len(expected_frames)} matching frame(s)')
    finally:
        pe.close()


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == '--verify-exe':
        verify_exe_icon(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if len(sys.argv) != 2:
        raise SystemExit('Usage: extract_tk_icon.py <output.ico> | --verify-exe <app.exe> <expected.ico>')
    dlls = candidate_tk_dlls()
    if not dlls:
        raise SystemExit('Tk DLL was not found in the Python installation')
    error = None
    for dll in dlls:
        try:
            num = extract_feather_icon(dll, Path(sys.argv[1]))
            print(f'OK: {num} native icon size(s)')
            return
        except (OSError, ValueError, KeyError) as e:
            error = e
            print(f'{dll}: {e}', file=sys.stderr)
    raise SystemExit(f'Could not extract Tk feather icon: {error}')


if __name__ == '__main__':
    main()
