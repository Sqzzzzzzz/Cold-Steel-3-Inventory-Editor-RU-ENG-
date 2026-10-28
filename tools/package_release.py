"""Package a verified Windows EXE and write its public SHA-256 checksum."""
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_info import VERSION


def package(executable, destination):
    executable = Path(executable)
    destination = Path(destination)
    if not executable.is_file() or executable.read_bytes()[:2] != b'MZ':
        raise ValueError('A Windows executable is required')
    destination.mkdir(parents=True,exist_ok=True)
    target = destination/f'CS3_Inventory_Editor_v{VERSION}_Windows.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        archive.write(executable,'CS3_Inventory_Editor.exe')
        for name in ('README.md','README_EN.md','LICENSE','CHANGELOG.md'):
            archive.write(ROOT/name,name)
        archive.writestr('VERSION.txt',VERSION+'\n')
    checksum = destination/'SHA256SUMS.txt'
    checksum.write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='ascii')
    return target


if __name__ == '__main__':
    print(package(ROOT/'dist/CS3_Inventory_Editor.exe',ROOT/'release'))
