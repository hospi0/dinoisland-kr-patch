# -*- coding: utf-8 -*-
r"""저장 화면(리모컨 메뉴 녹화/호출) 글자 판 한글화 (2026-10-10)
  글자 판 = BLDANIM.BIN 0x0602C00C(파일 0x1C00C)부터 16×16 4비트 칸 48개, 무압축(VDP1 VRAM 0x9000 으로 그대로 올라감).
  ★스테이트 VDP1_VRAM.bin 은 u16 바이트가 뒤집혀 있음 — 디스크 검색은 뒤집어서.
  칸 32‥47 = 本 体 カー トリ ッジ 録 画 呼 出 書 き 込 め ま せ ん · 30‥31 = RAM(그대로).
  색 번호는 원본 그대로: 채움 9 · 테두리 5(録画만 3) · 書き込めません 은 5 하나(테두리 없음).
  python tools/savefont.py   → work/gfx/kr/save_font.png 미리보기
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OFF = 0x1C00C; CELL = 128
GAL = r'C:\claude\utils\font\Galmuri-v2.40.3'
# (첫 칸, 칸 수, 글, 글꼴, 크기, 채움, 테두리, 자간, 굵게)
GROUPS = [
    (32, 2, '본체', 'Galmuri14.ttf', 15, 9, 5, 0, True),
    (34, 3, '카트리지', 'Galmuri11-Bold.ttf', 12, 9, 5, -1, False),
    (37, 2, '저장', 'Galmuri14.ttf', 15, 9, 3, 0, True),
    (39, 2, '로드', 'Galmuri14.ttf', 15, 9, 5, 0, True),
    (41, 7, '쓸 수 없습니다', 'Galmuri14.ttf', 15, 5, None, 1, False),
]


def strip(text, n, font, size, fill, edge, sp=0, bold=False):
    W = 16 * n; F = ImageFont.truetype(os.path.join(GAL, font), size)
    big = Image.new('L', (W * 3, 32), 0); d = ImageDraw.Draw(big); d.fontmode = '1'
    x = 0
    for ch in text:                                                    # 글자마다 찍고 자간 sp 만큼 당김/띄움
        d.text((x, 8), ch, font=F, fill=255); x += int(round(d.textlength(ch, font=F))) + sp
    m = np.array(big) > 0
    if bold: m[:, 1:] |= m[:, :-1].copy()                              # 가로 1px 굵게
    ys, xs = np.where(m); m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = m.shape; assert h <= 16 and w <= W, (text, w, h)
    full = np.zeros((16, W), bool); oy = (16 - h) // 2; ox = (W - w) // 2
    full[oy:oy + h, ox:ox + w] = m; m = full
    out = np.zeros((16, W), np.uint8)
    if edge is not None:
        p = np.pad(m, 1); e = np.zeros_like(m)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                e |= p[1 + dy:17 + dy, 1 + dx:W + 1 + dx]
        out[e] = edge
        assert w + 2 <= W and h + 2 <= 16, (text, w, h)
    out[m] = fill
    return out


def cells_of(img, n):
    return [img[:, k * 16:k * 16 + 16] for k in range(n)]


def pack(c):
    f = c.ravel(); return bytes((f[i] << 4 | f[i + 1]) for i in range(0, 256, 2))


def patch(exe):
    exe = bytearray(exe)
    for first, n, text, font, size, fill, edge, sp, bold in GROUPS:
        for k, c in enumerate(cells_of(strip(text, n, font, size, fill, edge, sp, bold), n)):
            exe[OFF + (first + k) * CELL:OFF + (first + k + 1) * CELL] = pack(c)
    return bytes(exe)


def unpack(b):
    a = np.frombuffer(b, np.uint8); return np.stack([a >> 4, a & 15], 1).ravel().reshape(16, 16)


def preview():
    pal = np.zeros((16, 3), np.uint8); pal[0] = (60, 90, 60); pal[3] = (40, 0, 0); pal[5] = (0, 60, 0); pal[9] = (60, 255, 60)
    org = open(os.path.join(ROOT, 'work', 'disc', 'BLDANIM.BIN'), 'rb').read(); new = patch(org)
    rows = []
    for src in (org, new):
        rows.append(np.concatenate([unpack(src[OFF + k * CELL:OFF + (k + 1) * CELL]) for k in range(30, 48)], 1))
    img = pal[np.concatenate([rows[0], np.full((4, rows[0].shape[1]), 0, np.uint8), rows[1]], 0)]
    os.makedirs(os.path.join(ROOT, 'work', 'gfx', 'kr'), exist_ok=True)
    p = os.path.join(ROOT, 'work', 'gfx', 'kr', 'save_font.png')
    Image.fromarray(img).resize((img.shape[1] * 5, img.shape[0] * 5), Image.NEAREST).save(p); print(p)


if __name__ == '__main__':
    preview()
