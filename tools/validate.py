#!/usr/bin/env python3
"""Validate all built Windows cursor assets without needing Windows."""
from __future__ import annotations
from pathlib import Path
import struct
import sys
from PIL import Image
from build import ANI_SIZES

ROOT = Path(__file__).resolve().parents[1]
SIZES = (32, 48, 64, 96, 128)
ROLES = ['arrow', 'help', 'appstarting', 'wait', 'crosshair', 'ibeam',
         'nwpen', 'no', 'sizens', 'sizewe', 'sizenwse', 'sizenesw',
         'sizeall', 'uparrow', 'hand', 'pin', 'person']
ALL_CUR = ROLES + ['extra']


def check_cur(data: bytes, sizes=SIZES):
    assert len(data) > 40
    assert struct.unpack_from('<HHH', data) == (0, 2, len(sizes)), 'unexpected CUR image count'
    from io import BytesIO
    hotspots = []
    expected_offset = 6 + 16 * len(sizes)
    for index, size in enumerate(sizes):
        w, h, ncolors, reserved, hx, hy, length, offset = struct.unpack_from('<BBBBHHII', data, 6 + 16 * index)
        assert w == size and h == size and reserved == 0 and 0 <= hx < size and 0 <= hy < size
        assert offset == expected_offset and offset + length <= len(data)
        header_size, bmp_w, bmp_h, planes, bpp, comp = struct.unpack_from('<IiiHHI', data, offset)
        assert (header_size, bmp_w, bmp_h, planes, bpp, comp) == (40, size, size*2, 1, 32, 0)
        assert length == 40 + size*size*4 + size*((size+31)//32*4)
        entry = struct.pack('<BBBBHHII', w, h, ncolors, reserved, hx, hy, length, 22)
        single = struct.pack('<HHH', 0, 2, 1) + entry + data[offset:offset+length]
        with Image.open(BytesIO(single)) as im:
            assert im.format == 'CUR' and im.size == (size, size) and im.getbbox(), 'cursor image is blank'
        hotspots.append((hx, hy))
        expected_offset += length
    assert expected_offset == len(data)
    return hotspots


def chunks(blob: bytes, start: int, end: int):
    p = start
    while p+8 <= end:
        cid, length = struct.unpack_from('<4sI', blob, p)
        q = p+8
        assert q+length <= end, 'RIFF chunk truncated'
        yield cid, blob[q:q+length]
        p = q+length+(length%2)
    assert p == end, 'RIFF trailing/invalid bytes'


def check_ani(path: Path):
    blob = path.read_bytes()
    assert blob[:4] == b'RIFF' and blob[8:12] == b'ACON'
    assert struct.unpack_from('<I',blob,4)[0] + 8 == len(blob)
    cks = dict(chunks(blob,12,len(blob)))
    info = struct.unpack('<9I',cks[b'anih'])
    assert info[0]==36 and info[1]==info[2]==8 and info[-1]==1
    assert len(cks[b'rate'])==8*4
    listing=cks[b'LIST']
    assert listing[:4]==b'fram'
    icons = list(chunks(listing,4,len(listing)))
    assert len(icons)==8 and all(tag==b'icon' for tag,data in icons)
    first_hotspot=None
    for _, data in icons:
        hs=check_cur(data, ANI_SIZES)
        if first_hotspot is None: first_hotspot=hs
        assert first_hotspot==hs, 'ANI hotspot changes during animation'


def check_windows_loading(directory: Path):
    """Catch files that pass binary validation but fail the real Windows loader."""
    import ctypes
    from ctypes import wintypes

    class IconInfo(ctypes.Structure):
        _fields_ = [('icon', wintypes.BOOL), ('x', wintypes.DWORD), ('y', wintypes.DWORD),
                    ('mask', wintypes.HANDLE), ('color', wintypes.HANDLE)]

    class Bitmap(ctypes.Structure):
        _fields_ = [('type', wintypes.LONG), ('width', wintypes.LONG),
                    ('height', wintypes.LONG), ('row_bytes', wintypes.LONG),
                    ('planes', wintypes.WORD), ('bits', wintypes.WORD), ('pixels', wintypes.LPVOID)]

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    gdi32 = ctypes.WinDLL('gdi32')
    user32.LoadImageW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.UINT,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadCursorFromFileW.argtypes = [wintypes.LPCWSTR]
    user32.LoadCursorFromFileW.restype = wintypes.HANDLE
    user32.DestroyCursor.argtypes = [wintypes.HANDLE]
    user32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(IconInfo)]
    gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID]
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]

    for path in sorted(directory.iterdir()):
        if path.suffix not in ('.cur', '.ani'):
            continue
        handle = user32.LoadCursorFromFileW(str(path))
        assert handle, f'Windows LoadCursorFromFile failed: {path.name}'
        user32.DestroyCursor(handle)
        for size in SIZES:
            handle = user32.LoadImageW(None, str(path), 2, size, size, 0x10)
            assert handle, f'Windows LoadImage failed: {path.name} at {size}px'
            info = IconInfo()
            try:
                assert user32.GetIconInfo(handle, ctypes.byref(info)), path.name
                bitmap = Bitmap()
                assert gdi32.GetObjectW(info.color, ctypes.sizeof(bitmap), ctypes.byref(bitmap))
                assert (bitmap.width, bitmap.height) == (size, size), path.name
                assert info.x < size and info.y < size, path.name
            finally:
                for bitmap_handle in (info.mask, info.color):
                    if bitmap_handle:
                        gdi32.DeleteObject(bitmap_handle)
                user32.DestroyCursor(handle)
    print('PASS: Windows native loading, requested bitmap sizes and hotspots for all CUR/ANI files')


def main():
    count = 0
    directory = ROOT/'cursors'/'multi'
    for name in ALL_CUR:
        check_cur((directory/f'{name}.cur').read_bytes())
        count+=1
    for name in ['appstarting','wait']:
        check_ani(directory/f'{name}.ani')
        count+=1
    for name in ALL_CUR:
        with Image.open(ROOT/'png'/f'{name}.png') as im:
            assert im.mode=='RGBA'
            lo,hi=im.getchannel('A').getextrema()
            assert lo==0 and hi>=250, f'{name} not transparent correctly'
    for file in ('Install.cmd','Restore.cmd','Uninstall.cmd','scripts/Install.ps1','scripts/Restore.ps1','README.md','assets/source_atlas.png','preview.png'):
        assert (ROOT/file).is_file(), f'{file} missing'
    print(f'PASS: {count} files (18 multi-resolution CUR + 2 multi-resolution ANI), 16 PNG poses + 2 reused states')
    print('PASS: CUR dimensions, hotspots, DIB + alpha, RIFF/ACON chunks and animation timing')
    if sys.platform == 'win32':
        check_windows_loading(directory)
    print('NOTE: This check does not apply the scheme or verify desktop animation playback.')


if __name__ == '__main__':
    main()
