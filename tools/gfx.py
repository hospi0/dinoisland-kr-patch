# -*- coding: utf-8 -*-
r"""그림 글자 한글(2026-10-10) — GI(tools/gi.py 로 풀고 gicodec 로 다시 압축)
  8비트 GI 다시 만들기: 색 번호 그림(h×w) → 8×8 셀 중복 합침 → 지도(셀 번호|0x8000) → enc_map · enc_cells_beam
  제한: 셀 ≤ 896(해제 버퍼 0x060D2000‥0x060E0000) · TITLET 파일 ≤ 32 KB(REPLAY 가 0x06068000 에 이어 실림)
"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gi, gicodec as C

LIMIT = {'TITLET': 0x8000}
MAXCELL = 896


def encode8(orig, idx):
    h, w = idx.shape
    npal = struct.unpack_from('>H', orig, 0x12)[0]
    head = orig[:0x14 + npal * 2]
    cells = []; seen = {}; mp = []
    for cy in range(h // 8):
        for cx in range(w // 8):
            c = idx[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].astype(np.uint8).tobytes()
            if c not in seen: seen[c] = len(cells); cells.append(c)
            mp.append(seen[c] | 0x8000)
    assert len(cells) <= MAXCELL, ('셀', len(cells))
    em = C.enc_map(mp); ec = C.enc_cells_beam(b''.join(cells), K=4)
    out = head + em + struct.pack('>H', len(cells)) + ec
    return out, len(cells)


def load(name):
    raw = open(os.path.join(ROOT, 'work', 'disc', name + '.GI'), 'rb').read()
    return raw, gi.decode(raw)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for f in ('TITLET', 'REPLAY', 'WARN1', 'WARN2'):
        raw, d = load(f)
        new, nc = encode8(raw, d['idx'])
        d2 = gi.decode(new)
        print(f, '왕복 %s · 셀 %d→%d · %d → %d B' % (np.array_equal(d2['idx'], d['idx']), d['nc'], nc, len(raw), len(new)))


# ================= 편집 =================
from PIL import Image, ImageDraw, ImageFont, ImageFilter
GAL11 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.ttf'
NANUM_B = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'
OUTDIR = os.path.join(ROOT, 'work', 'gfx', 'kr')


def text_mask(lines, font, size, w, h, spacing):
    """[(x 또는 None=가운데, y, 글)] → 1비트 글자 가면(안티앨리어싱 없음)"""
    F = ImageFont.truetype(font, size)
    im = Image.new('L', (w, h), 0); d = ImageDraw.Draw(im); d.fontmode = '1'
    for x, y, t in lines:
        tw = d.textlength(t, font=F)
        d.text(((w - tw) // 2 if x is None else x, y), t, font=F, fill=255)
    return np.array(im) > 0


def clear_text(idx, rects, bg):
    """지울 영역(그림과 안 겹치게 잡음) 안은 전부 바탕 — 글자 화소 색이 여러 가지라 색으로 고르지 않음"""
    for x0, y0, x1, y1 in rects:
        idx[y0:y1, x0:x1] = bg


WARN = {
    'WARN1': {'clear': [(0, 0, 320, 73), (0, 98, 160, 143), (0, 143, 129, 172)],
              'lines': [(None, 4, '본체(카트리지) RAM이 준비되지 않았습니다.'),
                        (None, 23, '멀티플레이어 화면에서 저장 데이터 관리 화면으로'),
                        (None, 42, '가서 「전부 지우기(초기화)」를 해 주세요.'),
                        (14, 112, 'START 버튼을 누르면'),
                        (14, 131, '멀티플레이어 화면으로'),
                        (14, 150, '돌아갑니다.')]},
    'WARN2': {'clear': [(0, 0, 320, 73), (0, 74, 160, 200)],
              'lines': [(None, 17, '백업 RAM 용량이 부족합니다.'),
                        (None, 36, '「다이나♥아이랑」 데이터를 기록하려면'),
                        (None, 55, '빈 용량을 6 이상 만들어 주세요.'),
                        (14, 79, '빈 용량을 만들려면'),
                        (14, 92, '멀티플레이어 화면에서'),
                        (14, 105, '저장 데이터 관리로 가서'),
                        (14, 118, '다른 게임의 데이터를'),
                        (14, 131, '지워 주세요.'),
                        (24, 153, '멀티플레이어 화면으로'),
                        (24, 172, '이대로 게임 시작')]},
}


def job_warn(name):
    raw, d = load(name); idx = d['idx'].copy(); pal = d['pal']
    bg = int(np.bincount(idx[0]).argmax())
    ink = [i for i, c in enumerate(pal) if (c & 31) < 4 and ((c >> 5) & 31) < 4 and ((c >> 10) & 31) < 4]
    black = ink[0]
    clear_text(idx, WARN[name]['clear'], bg)
    m = text_mask(WARN[name]['lines'], GAL11, 12, 320, 224, 0)
    for x0, y0, x1, y1 in WARN[name]['clear']:
        sub = m[y0:y1, x0:x1]; idx[y0:y1, x0:x1][sub] = black
    outside = m.copy()
    for x0, y0, x1, y1 in WARN[name]['clear']: outside[y0:y1, x0:x1] = False
    assert not outside.any(), (name, '글자가 지운 영역 밖으로 나감')
    new, nc = encode8(raw, idx)
    return new, nc, gi.rgb15(np.array(pal)[idx])


def job_spring():
    raw = open(os.path.join(ROOT, 'work', 'disc', 'SPRING.GI'), 'rb').read()
    w = 320; h = 224
    a = np.frombuffer(raw[16:16 + w * h * 2], '>u2').reshape(h // 8, w // 8, 8, 8).transpose(0, 2, 1, 3).reshape(h, w).copy()
    rgb = gi.rgb15(a).astype(int); bgc = a[2, 2]; bg = rgb[2, 2]
    A_ = a[183:207, 27:86].copy(); C_ = a[183:207, 164:293].copy()     # «©1997» · «, GAME ARTS»
    F = ImageFont.truetype(NANUM_B, 17); t = '타케모토 이즈미'
    tw = int(ImageDraw.Draw(Image.new('L', (1, 1))).textlength(t, font=F))
    gap1, gap2 = 5, 3
    total = A_.shape[1] + gap1 + tw + gap2 + C_.shape[1]; x0 = (w - total) // 2
    a[183:207, :] = bgc
    a[183:207, x0:x0 + A_.shape[1]] = A_
    kx = x0 + A_.shape[1] + gap1
    im = Image.new('L', (tw + 4, 24), 0); ImageDraw.Draw(im).text((0, 2), t, font=F, fill=255)
    al = np.array(im).astype(float) / 255
    ink = np.array([16, 8, 48], float)
    reg = gi.rgb15(a[183:207, kx:kx + tw + 4]).astype(float)
    mix = reg * (1 - al[..., None]) + ink * al[..., None]
    q = (np.round(mix / 8).astype(int).clip(0, 31))
    a[183:207, kx:kx + tw + 4] = (q[..., 0] | q[..., 1] << 5 | q[..., 2] << 10 | 0x8000) if (bgc & 0x8000) else (q[..., 0] | q[..., 1] << 5 | q[..., 2] << 10)
    cx = kx + tw + gap2
    a[183:207, cx:cx + C_.shape[1]] = C_
    out = a.reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).astype('>u2').tobytes()
    return raw[:16] + out + raw[16 + w * h * 2:], gi.rgb15(a)


def compare(name, before, after):
    os.makedirs(OUTDIR, exist_ok=True)
    b = Image.fromarray(before); a = Image.fromarray(after)
    s = Image.new('RGB', (640 + 8, 224), (0, 0, 0)); s.paste(b, (0, 0)); s.paste(a, (328, 0))
    s.resize((s.size[0] * 2, 448), Image.NEAREST).save(os.path.join(OUTDIR, '비교_%s.png' % name))


def run_simple():
    res = {}
    new, prev = job_spring()
    compare('SPRING', gi.decode(open(os.path.join(ROOT, 'work', 'disc', 'SPRING.GI'), 'rb').read())['rgb'], prev)
    res['/SPRING.GI'] = new
    for n in ('WARN1', 'WARN2'):
        new, nc, prev = job_warn(n)
        compare(n, load(n)[1]['rgb'], prev)
        d2 = gi.decode(new); assert np.array_equal(d2['rgb'], prev)
        res['/%s.GI' % n] = new; print(n, '셀 %d · %d B' % (nc, len(new)))
    return res


# ================= 타이틀 로고 «다이나♥아이랑» =================
import colorsys
from collections import deque
BHS = r'C:\claude\utils\font\logo\BlackHanSans.ttf'
LOGO_BOX = (84, 6, 244, 126)                      # x0, y0, x1, y1
HEART = (212, 60)                                 # 하트 안쪽 한 점(남김)


def classify(pal):
    rgb = np.array([[(c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8] for c in pal])
    cls = np.zeros(256, np.uint8)                 # 0 그 밖 · 1 판 · 2 테두리
    for i in range(len(pal)):
        r, g, b = rgb[i] / 255; h, s, v = colorsys.rgb_to_hsv(r, g, b); h *= 360
        if v < 0.35: cls[i] = 2
        elif s < 0.42 and v > 0.55 and 25 <= h < 70 and s > 0.12: cls[i] = 1      # 판 = 크림·황토(흰 구름 빼고)
    return cls, rgb


def nearest_idx(rgb, want, among=None):
    c = np.arange(len(rgb)) if among is None else np.array(among)
    dd = ((rgb[c] - np.array(want)) ** 2).sum(1)
    return int(c[dd.argmin()])


def logo_masks(idx, pal):
    cls, rgb = classify(pal)
    x0, y0, x1, y1 = LOGO_BOX
    sub = idx[y0:y1, x0:x1]; k = cls[sub]
    H, W = sub.shape
    bgm = np.zeros((H, W), bool); q = deque()
    for y in range(H):
        for x in range(W):
            if (y in (0, H - 1) or x in (0, W - 1)) and k[y, x] == 0:
                bgm[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W and not bgm[yy, xx] and k[yy, xx] == 0:
                bgm[yy, xx] = True; q.append((yy, xx))
    fill = (k == 0) & ~bgm
    # 하트 성분 찾기
    hy, hx = HEART[1] - y0, HEART[0] - x0
    heart = np.zeros_like(fill); q = deque([(hy, hx)]); heart[hy, hx] = True
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W and fill[yy, xx] and not heart[yy, xx]:
                heart[yy, xx] = True; q.append((yy, xx))
    def dil(m, r):
        o = m.copy()
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                o |= np.roll(np.roll(m, dy, 0), dx, 1)
        return o
    heart_all = dil(heart, 2) & ((k == 2) | heart)
    letters = (fill & ~heart)
    # ★옛 글자 색이 주인 성분만(양쪽 캐릭터 귀처럼 테두리에 갇힌 그림은 남김 — 사용자 2026-10-10)
    lab, n = label(letters); keep = np.zeros_like(letters)
    for c in range(1, n + 1):
        cm = lab == c
        if int(np.bincount(sub[cm]).argmax()) in LETTER_COLS: keep |= cm
    for c in range(1, n + 1):                           # 작은 광택 조각은 이웃 글자 성분에 붙어 있으면 같이
        cm = lab == c
        if not (keep & cm).any() and cm.sum() < 40 and (dil(cm, 2) & keep).any(): keep |= cm
    letters = keep
    letters_all = (letters | (dil(letters, 2) & (k == 2))) & ~heart_all
    return cls, rgb, letters, letters_all, heart_all, bgm


def label(m):
    """4방향 연결 성분 번호(scipy 없이)"""
    H, W = m.shape; lab = np.zeros((H, W), int); n = 0
    for y in range(H):
        for x in range(W):
            if m[y, x] and not lab[y, x]:
                n += 1; lab[y, x] = n; q = deque([(y, x)])
                while q:
                    a, b = q.popleft()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        yy, xx = a + dy, b + dx
                        if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not lab[yy, xx]:
                            lab[yy, xx] = n; q.append((yy, xx))
    return lab, n


def job_title_logo(idx, pal):
    x0, y0, x1, y1 = LOGO_BOX
    cls, rgb, letters, lall, heart, bgm = logo_masks(idx, pal)
    sub = idx[y0:y1, x0:x1]; k = cls[sub]; H, W = sub.shape
    # 원래 글자 색(성분별 최다 색) — x 순서, 위/아래 줄
    lab, n = label(letters)
    comps = []
    for c in range(1, n + 1):
        ys, xs = np.where(lab == c)
        if len(ys) < 25: continue
        vals = np.bincount(sub[lab == c], minlength=256)
        comps.append((ys.mean(), xs.mean(), int(vals.argmax()), len(ys)))
    # 지우기: 줄마다 «판 화소 중 가장 흔한 색»(나뭇결 = 가로 줄) — 그 줄에 판이 없으면 위아래 가까운 줄 것
    new = sub.copy()
    rowc = []
    for y in range(H):
        b = sub[y][(k[y] == 1) & ~lall[y] & ~heart[y]]
        rowc.append(int(np.bincount(b).argmax()) if len(b) >= 4 else None)
    for y in range(H):
        if rowc[y] is None:
            for dd in range(1, H):
                for yy in (y - dd, y + dd):
                    if 0 <= yy < H and rowc[yy] is not None: rowc[y] = rowc[yy]; break
                if rowc[y] is not None: break
        new[y][lall[y]] = rowc[y]
    idx[y0:y1, x0:x1] = new
    return comps, cls, rgb


GLYPHS = [  # (글자, 가운데 x, 가운데 y, 크기, 기울기°, 원래 글자 색 (줄, 순번))
    ('나', 183, 35, 48, -5, (0, 2)), ('이', 149, 37, 48, 4, (0, 1)),   # ★그리는 순서 = 겹침: 나 < 이 < 다(사용자 2026-10-10)
    ('다', 114, 35, 50, -8, (0, 0)),          # ★«다» 를 «이» 위에(나중에) 그림 — 겹치면 ㅏ 가로획이 묻혀 «디» 로 보임(사용자 2026-10-10)
    ('아', 124, 92, 52, 6, (1, 0)), ('이', 164, 94, 50, -4, (1, 1)), ('랑', 207, 91, 56, 5, (1, 2), (0.8, 120)),
]


def glyph_shape(ch, size, angle, blur=1.6, thr=90):
    F = ImageFont.truetype(BHS, size)
    im = Image.new('L', (size * 2, size * 2), 0)
    ImageDraw.Draw(im).text((size // 2, size // 3), ch, font=F, fill=255)
    im = im.rotate(angle, resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
    a = np.array(im) > thr
    ys, xs = np.where(a)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def dil(m, r):
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy * dy + dx * dx <= r * r + r:
                o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o


def job_title_new_logo(idx, pal, comps, cls, rgb):
    """옛 글자 색: 위 줄(y<60) 큰 성분들을 x 순으로 → だ い な / あ い ら ん"""
    cols = [[24, 16, 21], [22, 39, 23]]          # 원래 글자 색 번호: だ 빨강·い 보라·な 초록 / あ 파랑·い 초록·ら 주황 (성분 분석으로 확인)
    outline = nearest_idx(rgb, (16, 56, 24))
    drawn = np.zeros(idx.shape, bool)
    for g in GLYPHS:
        ch, cx, cy, size, ang, (ln, k) = g[:6]; bt = g[6] if len(g) > 6 else ()
        fill_i = cols[ln][min(k, len(cols[ln]) - 1)]
        fc = rgb[fill_i]
        hi_i = nearest_idx(rgb, tuple(np.minimum(255, fc * 0.55 + 255 * 0.45).astype(int)))
        sh = glyph_shape(ch, size, ang, *bt)
        h, w = sh.shape
        pad = 3
        canvas = np.zeros((h + 2 * pad, w + 2 * pad), bool); canvas[pad:pad + h, pad:pad + w] = sh
        ol = dil(canvas, 2)
        hl = canvas & ~np.roll(np.roll(canvas, 2, 0), 2, 1)          # 왼쪽 위 테두리 안쪽 = 광택
        hl &= np.roll(np.roll(canvas, -1, 0), -1, 1)
        y0 = cy - (h + 2 * pad) // 2; x0 = cx - (w + 2 * pad) // 2
        reg = idx[y0:y0 + h + 2 * pad, x0:x0 + w + 2 * pad]
        reg[ol] = outline; reg[canvas] = fill_i; reg[hl] = hi_i
        drawn[y0:y0 + h + 2 * pad, x0:x0 + w + 2 * pad] |= ol
    # (판 위 점 정리는 사용자 «원복» 지시로 뺌 2026-10-10)
    return idx


MENU_BOX = (128, 130, 222, 190)
MENU = [(133, 130, '처음부터'), (133, 145, '이어하기'), (133, 160, '리플레이'), (133, 175, '자동진행')]   # 띄어쓰기 없이(사용자 2026-10-10)
GAL14 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.ttf'


def job_title_menu(idx, pal):
    rgb = np.array([[(c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8] for c in pal])
    x0, y0, x1, y1 = MENU_BOX
    sub = idx[y0:y1, x0:x1]
    # 글자 둘레 중간 갈색이 나뭇결과 겹쳐 색으로는 못 가름 → 줄마다 판 양쪽 가장자리(글자 없는 x 112‥127 · 223‥230)의 흔한 색으로 통째로
    for y in range(y0, y1):
        side = np.concatenate([idx[y, 112:x0], idx[y, x1:231]])
        idx[y, x0:x1] = int(np.bincount(side).argmax())
    m = text_mask([(x, y, t) for x, y, t in MENU], GAL14, 14, 320, 224, 0)
    assert not m[:, :x0].any() and not m[:, x1:].any() and not m[:y0].any() and not m[y1:].any(), '메뉴 글자가 판 밖'
    idx[m] = 13                                          # 원래 글자 갈색(88,40,0)
    return idx


def job_title():
    raw, d = load('TITLET'); idx = d['idx'].copy()
    comps, cls, rgb = job_title_logo(idx, d['pal'])
    idx = job_title_new_logo(idx, d['pal'], comps, cls, rgb)
    idx = job_title_menu2(idx, d['pal'])
    idx = job_title_copyright(idx, d['pal'])
    import json                                          # ★국소 손질 목록(그 화소만) — 다른 기준은 안 바꿈
    t = json.load(open(os.path.join(HERE, 'title_touch.json'), encoding='utf-8'))
    for x, y, c in t['logo'] + t['gi']:
        if idx[y, x] != 13: idx[y, x] = c                # 글자 획(갈색 13)은 안 덮음 — 글꼴 15px 로 바뀌며 획과 겹친 좌표 6
    new, nc = encode8(raw, idx)
    assert len(new) <= LIMIT['TITLET'], ('TITLET', len(new))
    prev = gi.rgb15(np.array(d['pal'])[idx])
    assert np.array_equal(gi.decode(new)['rgb'], prev)
    compare('TITLET', d['rgb'], prev)
    return new, nc


# ================= 고침(2026-10-10 사용자): 귀 살리기 · 메뉴 글자만 · 판권 =================
LETTER_COLS = {24, 64, 16, 21, 22, 39, 41, 23}         # 옛 로고 글자 성분의 최다 색(빨강·분홍광택·보라·초록·파랑·초록·노랑·주황)


def mode_fill(idx, mask, rows=None):
    """가면 화소를 바깥에서 안으로 — 가면 아닌 8이웃 중 가장 흔한 색(양파 껍질)"""
    m = mask.copy(); H, W = idx.shape
    while m.any():
        ys, xs = np.where(m); done = []
        for y, x in zip(ys, xs):
            nb = [idx[yy, xx] for yy in range(max(0, y - 1), min(H, y + 2)) for xx in range(max(0, x - 1), min(W, x + 2))
                  if not m[yy, xx]]
            if nb: done.append((y, x, int(np.bincount(nb).argmax())))
        if not done: break
        for y, x, v in done: idx[y, x] = v; m[y, x] = False


def gray_cls(rgb):
    mx = rgb.max(1); mn = rgb.min(1); s = rgb.sum(1)
    lowsat = (mx - mn) <= 40
    return lowsat & (s > 390), lowsat & (s < 330), lowsat & (s >= 330) & (s <= 390)   # 흰 테두리 · 진한 글자 · 중간


def job_title_copyright(idx, pal):
    rgb = np.array([[(c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8] for c in pal])
    Hc, Dc, Mc = gray_cls(rgb)
    y0, y1, x0, x1 = 193, 213, 138, 312
    sub = idx[y0:y1, x0:x1]
    Hm = Hc[sub]; near2 = dil(Hm, 2); near1 = dil(Hm, 1)
    T = Hm | (Dc[sub] & near2) | (Mc[sub] & near1)
    T[:, 205 - x0:221 - x0] |= (Hc | Dc | Mc)[sub[:, 205 - x0:221 - x0]] & near2[:, 205 - x0:221 - x0]   # 泉 끝 남은 점
    orig = sub.copy()
    cut = lambda a, b: (orig[:, a - x0:b - x0].copy(), T[:, a - x0:b - x0].copy())
    A_ = cut(143, 188)                                  # «©1997»
    C_ = cut(221, 308)                                  # «,GAME ARTS» (219‥220 은 泉 끝 — 사용자 지적 «!» 조각)
    mode_fill(sub, T)
    # 한글: 진한 글자 35 + 흰 테두리 2 (원본 색)
    F = ImageFont.truetype(GAL11, 12); t = '타케모토 이즈미'
    tw = int(ImageDraw.Draw(Image.new('L', (1, 1))).textlength(t, font=F))
    im = Image.new('L', (tw + 4, 20), 0); dd = ImageDraw.Draw(im); dd.fontmode = '1'; dd.text((2, 3), t, font=F, fill=255)
    g = np.array(im) > 0; halo = dil(g, 1) & ~g
    right = int(np.where(g.any(0))[0].max())          # ★«미» 끝을 쉼표 바로 앞(x 219)에 — 지운 자리를 글자로 덮어 찌꺼기 최소(사용자 2026-10-10)
    kx = 219 - right; ky = 194
    def put(px, m, x, y):
        reg = idx[y:y + px.shape[0], x:x + px.shape[1]]; reg[m] = px[m]
    put(C_[0], C_[1], 221, y0)
    reg = idx[ky:ky + 20, kx:kx + tw + 4]; reg[halo] = 2; reg[g] = 35
    put(A_[0], A_[1], kx - 3 - A_[0].shape[1], y0)
    return idx


def job_title_menu2(idx, pal):
    """글자 화소와 둘레 1px 만 — 같은 줄 ±8px 의 판 색으로"""
    rgb = np.array([[(c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8] for c in pal])
    x0, y0, x1, y1 = MENU_BOX
    sub = idx[y0:y1, x0:x1]; s = rgb[sub].sum(2)
    m = dil(s < 330, 1) & (s < 450)
    src = sub.copy()
    for y, x in zip(*np.where(m)):
        win = [src[y, xx] for xx in range(max(0, x - 8), min(sub.shape[1], x + 9)) if not m[y, xx]]
        if win: sub[y, x] = int(np.bincount(win).argmax())
    mt = text_mask([(x, y, t) for x, y, t in MENU], GAL14, 15, 320, 224, 0)   # ★15px(갈무리14 제 크기)
    mt |= np.roll(mt, 1, 1)                             # ★가로 1px 덧그려 굵게(사용자 «더 두껍게» 2026-10-10)
    # ★점 찌꺼기(옛 글자 흐린 가장자리, 사용자 2026-10-10): 같은 줄 ±4px 에서 한 번만 나오는 화소 → 그 창의 흔한 색
    #   (나뭇결·체크 무늬는 같은 줄에 같은 색이 되풀이돼 안 걸림)
    for _ in range(2):
        src = idx.copy()
        for y in range(y0, y1):
            for x in range(x0, x1):
                if mt[y, x]: continue
                win = [src[y, xx] for xx in range(x - 4, x + 5) if xx != x and not mt[y, xx]]
                if win and win.count(src[y, x]) == 0:
                    idx[y, x] = int(np.bincount(win).argmax())
    idx[mt] = 13
    return idx
