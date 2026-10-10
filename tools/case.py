# -*- coding: utf-8 -*-
r"""선택지 그림 CASE###.SP (2026-10-10)
  꼴: +0 'SP' · +2 10 08 · +4 u16 칸 수(= 올림(폭/16)+1) · +6 u16 줄 수(= 선택지 수) · +8 u16 폭 · +10 u16 높이(= 줄×16) · +12 0
       +16 폭×높이 바이트(1 = 글자, 0xFF = 투명). 게임이 VDP1 8비트 스프라이트로 그리고 말풍선 틀은 폭·높이를 따라 붙인다(선택지.state1).
  대본 DINA.CIT `@NNN,x,y,…` = CASE NNN 을 (x,y) 에 → 말풍선 오른쪽 끝 = x + 폭 + 8 ≤ 320 → 폭 ≤ 312 − x.
  원문 = 그림을 눈으로 옮김(2026-10-10). 번역 → work/text/choice.tsv 의 «번역» 열.
  python tools/case.py extract   → work/text/choice.tsv
  python tools/case.py preview   → work/case/kr_*.png (번역 있는 것만)
"""
import collections, os, re, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc

FONT = ImageFont.truetype(r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri14.ttf', 15)   # ★갈무리14 는 15px 도트(14px 면 획 깨짐 — 사용자 2026-10-10)
TSV = os.path.join(ROOT, 'work', 'text', 'choice.tsv')
HEAD = 'id\t줄\t원문\t최대폭px\t번역'

SRC = {
    0: ['セーブする', 'しない'],
    1: ['とりあえず自己紹介！', 'でもやっぱり歌う'],
    2: ['予告編をもっている', 'もってない'],
    3: ['もっと聞く', '歌に戻る'],
    4: ['ぜひしてほしい', 'そろそろ歌う'],
    5: ['ナレーションに聞く', 'いいかげんに戻る'],
    6: ['自己紹介させる', 'させなくてもいい'],
    7: ['もっと聞く', '本題に戻る'],
    8: ['ナレーションに聞く', '本題に戻る'],
    9: ['人物紹介する', 'そのまま進む'],
    10: ['がんばって考える', '笑ってゴマかす', 'あんじぇに賛成する'],
    11: ['人物紹介する', 'そのまま進む'],
    12: ['線香花火をやる', 'ねずみ花火をやる', 'ロケット花火をやる'],
    13: ['シャワーを浴びる', 'お風呂に入る', 'どちらも入らない'],
    14: ['人物紹介する', 'そのまま進む'],
    15: ['お風呂', '考古学', '女の子'],
    16: ['汗をかく', '運動する', '寝る'],
    17: ['人物紹介する', 'そのまま進む'],
    18: ['お風呂', '考古学', '女の子'],
    19: ['話を聞く', '話を聞かない', '正体をあばく'],
    20: ['トランペットにする', 'フルートにする', 'ウクレレにする'],
    21: ['やっぱりトランペット', 'やっぱりフルート', 'やっぱりウクレレ'],
    22: ['練習を続ける', '観察する'],
    23: ['ちょっといじける', 'それでもくじけない'],
    24: ['ネズミだと思う', 'ネコのような気がする', 'プニュームキンかも…'],
    25: ['練習をする', 'もう寝る'],
    26: ['松にする', '竹にする', '梅にする'],
    27: ['教えてあげない', '教えてあげる'],
    28: ['感謝しておく', '笑ってごまかす'],
    29: ['楽しい曲を吹く', '勇ましい曲を吹く'],
    30: ['寂しい曲を吹く', '勇ましい曲を吹く'],
    31: ['激しい曲を吹く', '楽しい曲を吹く'],
    32: ['楽しい曲を吹く', '寂しい曲を吹く'],
    33: ['さわやかな曲を吹く', '変な曲を吹く'],
    34: ['楽しい曲を吹く', '変な曲を吹く'],
    35: ['寂しい曲を吹く', '変な曲を吹く'],
    36: ['激しい曲をひく', '変な曲をひく'],
    37: ['楽器を持って行く', '持って行かない'],
    38: ['森のような気がする…', '海だったような…', '山かもしれない…'],
    39: ['ボタンを押してみる', '見なかったことにする'],
    40: ['地引網に混ざる', '潮干狩を続ける'],
    41: ['ジャングルに行ってみる', '湖に行ってみる'],
    42: ['卵を取る', '卵を取らない', 'もう一度突いてみる'],
    43: ['ジャングルに行ってみる', '湖に行ってみる'],
    44: ['助けてあげる', '水島に頼む', 'ことわる'],
    45: ['やっぱりやめておく', '怪しそうだけど持って帰る'],
    46: ['湖に行ってみる', '海に行ってみる'],
    47: ['最後まで助けてあげる', '気まずいけど逃げる'],
    48: ['やっぱりやめておく', '持って帰ってみる'],
    49: ['湖に行ってみる', 'ジャングルに行ってみる'],
    50: ['あんじぇの後を追う', 'ここで待ってみる'],
    51: ['ジャングルに行ってみる', '湖に行ってみる'],
    52: ['確かめるために待つ', '早く逃げる'],
    53: ['ジャングルに行ってみる', '海に行ってみる'],
    54: ['大きいのがよさそう', '無難そうな中ぐらいを取る', '小さいのにしておく'],
    55: ['湖に行ってみる', '海に行ってみる'],
    56: ['確かめてみる', '無視して先に行く'],
    57: ['小さな宝箱', '中くらいの宝箱', '大きな宝箱'],
    58: ['今回はパスしておく', '持って帰ってみる'],
    59: ['行ってみる', 'やめておく'],
    60: ['自分が持って帰る', 'あんじぇにゆずる'],
    61: ['金の卵', '銀の卵', '普通の卵'],
    62: ['勇気をもって入る', 'ここはやめておく'],
    63: ['こわいので逃げる', '隠れて様子を見る'],
    64: ['かわいそうなので拾う', '怪しそうなのでやめておく'],
    65: ['赤いドアのはず', '青いドアのはず'],
    66: ['自信なさそうに答える', '自信たっぷりに答える'],
    67: ['歌をうたう', '楽器を演奏する', '呼びかけてみる'],
    68: ['楽しい歌をうたう', '燃える歌をうたう', 'こわい歌をうたう'],
    69: ['もう一度吹く', 'こんどは歌ってみる', '卵を取りに行く'],
    70: ['吹き続ける', '歌をうたう'],
    71: ['子守唄をうたう', '歌合戦を挑む', '笑ってごまかす'],
    72: ['楽しい歌をうたう', '燃える歌をうたう'],
    73: ['音符もようの卵', 'ハートもようの卵', 'お日様もようの卵'],
    76: ['グーを出す', 'チョキを出す', 'パーを出す'],
    77: ['拍手する', '笑う'],
}


def files():
    return {int(n[-6:-3]): n for n, _, _ in disc.files() if re.search(r'CASE\d{3}\.SP$', n)}


def maxw():
    b = open(os.path.join(ROOT, 'work', 'disc', 'DINA.CIT'), 'rb').read()
    pos = collections.defaultdict(set)
    for n, x, y in re.findall(rb'@(\d{3}),(\d+),(\d+)', b): pos[int(n)].add(int(x))
    return {k: 312 - max(v) for k, v in pos.items()}


def head(b):
    return struct.unpack_from('>4H', b, 4)            # 칸 수, 줄 수, 폭, 높이


def extract():
    fs = files(); mw = maxw(); rows = [HEAD]
    for k in sorted(fs):
        b = disc.read(fs[k]); _, n, w, h = head(b)
        assert len(SRC[k]) == n and h == 16 * n, (k, n, h)
        for i, t in enumerate(SRC[k]):
            rows.append('CASE%03d\t%d\t%s\t%d\t' % (k, i + 1, t, mw.get(k, 296)))
    open(TSV, 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
    print('선택지 %d개 · 줄 %d → %s' % (len(fs), len(rows) - 1, TSV))


def width(t):
    return int(round(ImageDraw.Draw(Image.new('L', (1, 1))).textlength(t, font=FONT)))


def render(lines):
    """한국어 줄들 → (폭, 높이, 바이트) — 폭 8 배수, 줄마다 16 px, 글자 색 1·나머지 0xFF"""
    w = (max(width(t) for t in lines) + 7) // 8 * 8; h = 16 * len(lines)
    im = Image.new('L', (w, h), 0); d = ImageDraw.Draw(im); d.fontmode = '1'
    for i, t in enumerate(lines):
        d.text((0, i * 16), t, font=FONT, fill=255)
    a = np.array(im) > 0
    return w, h, np.where(a, 1, 0xFF).astype(np.uint8).tobytes()


def build_sp(orig, lines):
    w, h, px = render(lines)
    hd = bytearray(orig[:16])
    struct.pack_into('>4H', hd, 4, -(-w // 16) + 1, len(lines), w, h)
    return bytes(hd) + px, w


def table():
    out = collections.defaultdict(dict)
    for ln in open(TSV, encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t')
        if len(c) >= 5 and c[4].strip():
            out[int(c[0][4:])][int(c[1])] = c[4].strip()
    return out


def preview():
    fs = files(); tb = table(); mw = maxw(); bad = []
    os.makedirs(os.path.join(ROOT, 'work', 'case'), exist_ok=True)
    for k, d in sorted(tb.items()):
        lines = [d.get(i + 1, '') for i in range(len(SRC[k]))]
        if not all(lines): bad.append((k, '줄 빠짐')); continue
        sp, w = build_sp(disc.read(fs[k]), lines)
        if w > mw.get(k, 296): bad.append((k, '폭 %d > %d' % (w, mw.get(k, 296))))
        _, _, w2, h2 = head(sp); a = np.frombuffer(sp[16:], np.uint8).reshape(h2, w2)
        Image.fromarray(np.where(a == 1, 0, 255).astype(np.uint8)).resize((w2 * 2, h2 * 2), Image.NEAREST).save(
            os.path.join(ROOT, 'work', 'case', 'kr_%03d.png' % k))
    print('번역 %d개 · 문제 %s' % (len(tb), bad or '없음'))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'extract': extract, 'preview': preview}[sys.argv[1]]()
