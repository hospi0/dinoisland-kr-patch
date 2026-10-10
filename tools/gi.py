# -*- coding: utf-8 -*-
r"""GI 그림(2026-10-10) — 'GI' · +3 색 깊이(0x10 = 15비트 무압축 8×8 셀 순서 / 0x08 = 8비트) · +8 폭 · +10 높이
  8비트: +0x12 팔레트 수 · +0x14 팔레트(15비트) · 압축 지도(u16, 해제기 0x06019078) · u16 셀 수 · 압축 셀(해제기 0x06018ECC, 셀 64 B)
  해제는 게임 코드를 sh2sim 으로 그대로 돌림.  python tools/gi.py → work/gfx/<이름>.png
"""
import os, struct, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sh2sim as S
EXE = os.path.join(ROOT, 'work', 'disc', 'BLDANIM.BIN')


def rgb15(a):
    a = np.asarray(a, np.uint32)
    return np.dstack([(a & 31) << 3, ((a >> 5) & 31) << 3, ((a >> 10) & 31) << 3]).astype(np.uint8)


def decode(gi):
    w, h = struct.unpack_from('>HH', gi, 8)
    if gi[3] == 0x10:                                   # 머리 높이(SPRING 229)와 달리 자료는 224행
        h = (len(gi) - 16) // 2 // w // 8 * 8
        a = np.frombuffer(gi[16:16 + w * h * 2], '>u2').reshape(h // 8, w // 8, 8, 8).transpose(0, 2, 1, 3).reshape(h, w)
        return {'w': w, 'h': h, 'rgb': rgb15(a)}
    exe = open(EXE, 'rb').read()
    m = S.Mem(); m.add(0x06000000, 0x100000)
    m._f(0x06010000)[0][0x10000:0x10000 + len(exe)] = exe
    m._f(0x06060000)[0][0x60000:0x60000 + len(gi)] = gi
    npal = struct.unpack_from('>H', gi, 0x12)[0]
    pal = struct.unpack_from('>%dH' % npal, gi, 0x14)
    r, _ = S.run(m, 0x06019078, regs=[0, 0, 0, 0, 0x060E0000, 0x06060000 + 0x14 + npal * 2] + [0] * 9 + [0x060FF000])
    me = r[0] - 0x06060000
    mp = [m.r16(0x060E0000 + 2 * i) for i in range((w // 8) * (h // 8))]
    nc = struct.unpack_from('>H', gi, me)[0]
    r2, _ = S.run(m, 0x06018ECC, regs=[0, 0, 0, 0, 0x06080000, 0x06060000 + me + 2] + [0] * 9 + [0x060FF000])
    cells = bytes(m.r8(0x06080000 + i) for i in range(nc * 64))
    img = np.zeros((h, w), np.uint8)
    for k, v in enumerate(mp):
        cy, cx = divmod(k, w // 8)
        v &= 0x7FFF                                       # 비트 15 = 특수 기능 비트(뒤집기 아님)
        if v < nc: img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = np.frombuffer(cells[v * 64:v * 64 + 64], np.uint8).reshape(8, 8)
    return {'w': w, 'h': h, 'pal': pal, 'map': mp, 'cells': cells, 'nc': nc, 'idx': img,
            'rgb': rgb15(np.array(pal)[img]), 'map_len': me - 0x14 - npal * 2, 'end': r2[0] - 0x06080000}


if __name__ == '__main__':
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    for f in ('SPRING', 'TITLET', 'REPLAY', 'WARN1', 'WARN2'):
        d = decode(open(os.path.join(ROOT, 'work', 'disc', f + '.GI'), 'rb').read())
        Image.fromarray(d['rgb']).save(os.path.join(ROOT, 'work', 'gfx', f + '.png'))
        print(f, d['w'], d['h'], '셀 %d' % d.get('nc', 0), '지도 최대 %s' % (hex(max(d['map'])) if 'map' in d else '-'))
