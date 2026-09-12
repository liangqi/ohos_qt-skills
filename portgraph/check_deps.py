# -*- coding: utf-8 -*-
"""查询 portgraph DB：tdesktop 真实依赖清单在 Harmonybrew/cmd-pkgs 的产物可用性"""
import sqlite3
import sys

conn = sqlite3.connect('workspace/portgraph.db')
names = [
    # ffmpeg 编解码依赖
    'opus', 'rnnoise', 'dav1d', 'openh264', 'libvpx',
    # 音频
    'openal-soft', 'openal',
    # 图像格式
    'libwebp', 'webp', 'libheif', 'libde265', 'libavif', 'libjxl', 'jxl',
    'lcms2', 'little-cms', 'jpeg-turbo', 'libjpeg-turbo', 'mozjpeg', 'jpeg',
    # 文本/杂项
    'hunspell', 'cmark', 'cmark-gfm', 'ada', 'boost', 'lz4', 'xxhash',
    'minizip', 'kcoreaddons', 'kf5-kcoreaddons', 'kf6-kcoreaddons',
    # 重型/Telegram 专属
    'tlottie', 'tdlib', 'tgcalls', 'tg_owt', 'libcbor', 'libfido2', 'fido2',
    'range-v3',
    # 传递依赖
    'glib', 'libiconv', 'iconv', 'protobuf', 'abseil', 'fontconfig',
    'freetype', 'icu4c', 'brotli', 'libpng', 'zstd', 'xz', 'libzip',
    'expat', 'ffmpeg', 'openssl@3', 'zlib', 'libmicrohttpd', 'sdl2',
]
rows = conn.execute(
    "SELECT id,name,source,port_status,version,artifact_url FROM nodes WHERE kind='package'"
).fetchall()
byname = {}
for r in rows:
    byname.setdefault(r[1].lower(), []).append(r)

found, missing = [], []
for n in names:
    hits = byname.get(n)
    if hits:
        for h in hits[:3]:
            art = 'BOTTLE' if h[5] else 'no-url'
            print(f'{h[1]:20s} src={h[2]:12s} port={h[3]:9s} ver={str(h[4])[:14]:14s} {art}')
        found.append(n)
    else:
        print(f'{n:20s} NOT-FOUND-IN-DB')
        missing.append(n)
print(f'\n=== found={len(found)} missing={len(missing)} ===')
print('missing:', ', '.join(missing))
