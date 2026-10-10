# -*- coding: utf-8 -*-
r"""다이노 아일랜드 빌드 (2026-10-10 뼈대)
  입력:  work/text/voice.tsv «번역» 열(빈칸 = 자막 없음) · work/text/choice.tsv «번역» 열
  ① 음성: 번역 있는 ST2 마다 머리에 DSUB 묶음(poc2.payload 꼴) — 줄(받아쓰기 조각) 하나가 두 줄 넘으면 쪽을 나누고 글자 수 비율로 시각을 나눔.
         시각 = 초×60 + 늘린 머리 무음(머리 바이트/735), 쪽 최소 0.8초, 끝은 0.3초 남기되 다음 줄 시작을 넘지 않음.
  ② 선택지: CASE###.SP 를 한글 그림으로(case.build_sp) — 최대 폭(312 − 대본 x) 넘으면 빌드 실패.
  ③ 실행 파일: poc2 훅(머리 훅·VBI 감싸개·그리기).
  ④ 디스크: iso.relayout(전체 재배치) → work/out.
  규칙: 부호 뒤 공백 지움 · 글꼴(갈무리11)에 없는 글자 = 빌드 실패 · 쪽 글자 번호 9비트(음성당 서로 다른 글자 511 이하, 셋째 바이트 비트 2).
  python tools/build.py [--write] [--only S00100,…]
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.append(r'C:\claude\project\burningrangers-kr-patch\tools')
import glyphpack as G
import disc, iso, case, rules
import poc as P, poc2 as Q

G.MAXW = 300                                      # NBG3 40칸(320 px) 안 — w8 = (폭+4+7)//8 ≤ 39
VOICE_TSV = os.path.join(ROOT, 'work', 'text', 'voice.tsv')
PUNCT_SP = re.compile(r'([,.!?:;)\]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) +')
MINP = 0.8; LINGER = 0.3


def clean(t):
    return PUNCT_SP.sub(r'\1', t.strip())


def check_glyphs(t, where):
    for c in t:
        if c == ' ': continue
        if not any(G.glyph(c)): raise SystemExit('글꼴에 없는 글자 %r — %s' % (c, where))


def voice_rows():
    out = {}
    for ln in open(VOICE_TSV, encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t')
        if len(c) < 5 or not c[4].strip(): continue
        v = c[0].rsplit('_', 1)[0]
        ko = clean(c[4]); check_glyphs(ko, c[0])
        if re.search(r'\(\?\)|\(원문', ko): raise SystemExit('번역 메모가 남음 %s: %s' % (c[0], ko))
        if rules.check(ko): raise SystemExit('용어 규칙 위반 %s %s — tools/merge_ko.py 로 다시 합칠 것' % (c[0], rules.check(ko)))
        out.setdefault(v, []).append((float(c[1]), float(c[2]), ko, c[0]))
    return out


def pages_for(rows):
    """→ [(t0초, t1초, [줄…])]"""
    rows = sorted(rows); out = []
    for i, (s, e, ko, rid) in enumerate(rows):
        nxt = rows[i + 1][0] if i + 1 < len(rows) else None
        pg = G.pages_of(ko)
        lens = [max(1, len(''.join(p).replace(' ', ''))) for p in pg]; tot = sum(lens); acc = 0
        end = max(e + LINGER, s + MINP * len(pg))
        if nxt is not None: end = min(end, max(nxt, s + MINP * len(pg)))
        for p, L in zip(pg, lens):
            t0 = s + (end - s) * acc / tot; acc += L
            out.append([t0, s + (end - s) * acc / tot, p])
    for a, b in zip(out, out[1:]):                    # 겹침 없애기
        if a[1] > b[0]: a[1] = b[0]
    return [(a, b, p) for a, b, p in out]


def voice_payload(v, rows):
    pg = pages_for(rows)
    fr = lambda t: int(round(t * 60))
    pages = [(fr(a), fr(b), p) for a, b, p in pg]
    nglyph = len({c for _, _, p in pages for c in ''.join(p) if c != ' '})
    if nglyph > 511: raise SystemExit('%s 서로 다른 글자 %d > 511' % (v, nglyph))
    pay0 = Q.payload(pages, 0)
    head = 0x30 + len(pay0); delay = round(head / 735)
    pay = Q.payload(pages, delay); assert len(pay) == len(pay0)
    nglyph = len({c for _, _, p in pages for c in ''.join(p) if c != ' '})
    if nglyph > 511: raise SystemExit('%s 서로 다른 글자 %d > 511' % (v, nglyph))
    if len(pay) > Q.SUBMAX: raise SystemExit('%s 묶음 %d B > %d' % (v, len(pay), Q.SUBMAX))
    return pay, len(pages), nglyph


def st2_with(orig, pay):
    h = bytearray(orig[:0x30]); new_head = 0x30 + len(pay)
    struct.pack_into('>I', h, 4, new_head)
    struct.pack_into('>I', h, 0xC, struct.unpack_from('>I', orig, 0xC)[0] + new_head - 0x30)
    return bytes(h) + pay + orig[0x30:]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    only = None
    if '--only' in sys.argv: only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    fs = {os.path.basename(n)[:-4]: n for n, _, _ in disc.files() if n.endswith('.ST2')}
    files = {}
    vr = voice_rows(); npg = 0; big = 0
    for v, rows in sorted(vr.items()):
        if only and v not in only: continue
        pay, n, g = voice_payload(v, rows); npg += n; big = max(big, len(pay))
        files[fs[v]] = st2_with(disc.read(fs[v]), pay)
    print('① 음성 %d개 · 쪽 %d · 가장 큰 묶음 %d B' % (len(files), npg, big))
    cf = case.files(); mw = case.maxw(); tb = case.table(); nc = 0
    for k, d in sorted(tb.items()):
        lines = [clean(d.get(i + 1, '')) for i in range(len(case.SRC[k]))]
        if not all(lines): raise SystemExit('CASE%03d 번역 줄 빠짐' % k)
        for t in lines: check_glyphs(t, 'CASE%03d' % k)
        sp, w = case.build_sp(disc.read(cf[k]), lines)
        if w > mw.get(k, 296): raise SystemExit('CASE%03d 폭 %d > %d' % (k, w, mw.get(k, 296)))
        files[cf[k]] = sp; nc += 1
    print('② 선택지 %d개' % nc)
    import gfx                                           # ④ 그림: 첫 로고 판권·경고 2장·타이틀
    files.update(gfx.run_simple())
    t, nc = gfx.job_title(); files['/TITLET.GI'] = t
    print('④ 그림 SPRING·WARN1·WARN2·TITLET(%d B, 셀 %d)' % (len(t), nc))
    import hook                                          # ★VDP1 스프라이트 자막(VDP2 NBG3 판은 화면 깨짐 2026-10-10)
    new, res, lab = hook.build_exe(); files['/BLDANIM.BIN'] = new
    print('③ BLDANIM %d B' % len(new))
    if '--write' in sys.argv:
        iso.relayout(P.OUT, files)


if __name__ == '__main__':
    main()
