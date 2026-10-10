# -*- coding: utf-8 -*-
r"""다이노 아일랜드 자막 PoC 2 (2026-10-10) — 자막 자료를 «음성 ST2 머리»에 싣는다.
  ST2 머리 처리기(BLDANIM 0x060147DC)는 머리 0x80 B 를 0x06030B70 으로 memcpy(리터럴 0x060148EC → 0x06018EA4) 한 뒤
  머리 +6 «데이터 시작» 바이트만큼 고리 버퍼 앞을 0 으로 지워 무음 재생한다.
  ⇒ 머리를 늘려 0x30 뒤에 자막 묶음('DSUB')을 넣고, memcpy 리터럴을 훅으로 바꿔 묶음을 상주 버퍼 SUBBUF 로 복사 → 원래 memcpy.
  묶음:  +0 'DSUB' · +4 u16 쪽 수 · +12 u16 글꼴 자리 · +16 쪽 표[쪽 수] (u16 t0, u16 t1, u16 쪽 자리, u16 0)
         쪽 = glyphpack 꼴(u8 w8, u8 nrow, u8 c0, u8 글자 수, 글자마다 3 B) · 글꼴 = 글자마다 18 B(12×12 1비트)
         t = 1/60초, 시계 0x06046E74(음성 재생 위치) 기준 — 늘린 머리만큼(바이트/735 프레임) 무음이 붙으므로 더해 둔다.
  그리기 = 버닝 레인저 draw(1비트 버퍼에 찍기 → 3×3 테두리 → 4비트 셀) 를 NBG3 배치(poc.py)에 맞춤, 아래쪽(27−nrow 행)부터.
  ★시험: 묶음 뒤에 0 아닌 채움 FILL B 를 붙여 «머리 처리 때 아직 안 온 섹터»가 소리로 새는지 귀로 확인(시작에 잡음 = 늦은 섹터).
  python tools/poc2.py [--write]
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.append(r'C:\claude\project\burningrangers-kr-patch\tools')
import glyphpack as G
from sh2asm import A
import sh2sim as S
import disc, iso
import poc as P

MEMCPY = 0x06018EA4; MEMCPY_LIT = 0x060148EC
SUBBUF = P.RES + 0x2000; SUBMAX = 0x8000          # 상주 묶음 32 KB(0x0604B000‥0x06053000)
BUF = P.RES + 0x1800; BSTR = 52                   # 1비트 쪽 버퍼 52 B × 34행
FILL = 12 * 1024
STREAMING = 0x06031CD0                                # 스트림 구조 0x06031BF0+0xE0: 재생 중 1(오프닝·대사) / 0(타이틀)
VOICE = '/A_PART/S00100.ST2'
OUT = P.OUT


def payload(pages, delay):
    lay = [G.layout(l) for _, _, l in pages]
    gl = []; gi = {}
    for _, _, chars in lay:
        for c, _, _ in chars:
            if c not in gi: gi[c] = len(gl); gl.append(c)
    recs = []
    for w8, nrow, chars in lay:
        assert w8 * nrow <= 255 and w8 <= 40
        c0 = (40 - w8) // 2
        r = bytes([w8, nrow, c0, len(chars)])
        for c, x, ln in chars:
            r += bytes([gi[c] & 0xFF, x & 0xFF, (x >> 8) | ln << 1 | (gi[c] >> 8) << 2])   # 비트 2 = 글자 번호 9번째(최대 511)
        recs.append(r + bytes(-len(r) % 4))
    head = 16 + 8 * len(pages)
    offs = []; o = head
    for r in recs: offs.append(o); o += len(r)
    gofs = o
    body = b''.join(recs) + b''.join(G.gbytes(c) for c in gl)
    tab = b''.join(struct.pack('>HHHH', t0 + delay, t1 + delay, offs[i], 0) for i, (t0, t1, _) in enumerate(pages))
    b = b'DSUB' + struct.pack('>HH', len(pages), delay) + bytes(4) + struct.pack('>H', gofs) + bytes(2) + tab + body
    return b + bytes(-len(b) % 4)


def st2(orig, pay):
    """머리 0x30 + 묶음 + 채움 → «데이터 시작» = 새 머리 길이, +0xC 길이는 그만큼 늘림(파일 처음부터 세는 남은 바이트)"""
    h = bytearray(orig[:0x30])
    fill = bytes([0x5A, 0xA5]) * (FILL // 2)
    new_head = 0x30 + len(pay) + len(fill)
    struct.pack_into('>I', h, 4, new_head)
    struct.pack_into('>I', h, 0xC, struct.unpack_from('>I', orig, 0xC)[0] + new_head - 0x30)
    return bytes(h) + pay + fill + orig[0x30:], new_head


mov = lambda m, n: 0x6003 | n << 8 | m << 4
ldb = lambda m, n: 0x6000 | n << 8 | m << 4
ldbp = lambda m, n: 0x6004 | n << 8 | m << 4
stb = lambda m, n: 0x2000 | n << 8 | m << 4
ldb0 = lambda m, d: 0x8400 | m << 4 | d
stb0 = lambda n, d: 0x8000 | n << 4 | d
exb = lambda m, n: 0x600C | n << 8 | m << 4
exw = lambda m, n: 0x600D | n << 8 | m << 4
OR = lambda m, n: 0x200B | n << 8 | m << 4
AND = lambda m, n: 0x2009 | n << 8 | m << 4
ADD = lambda m, n: 0x300C | n << 8 | m << 4
addi = lambda n, i: 0x7000 | n << 8 | (i & 0xFF)
movi = lambda n, i: 0xE000 | n << 8 | (i & 0xFF)
shll = lambda n: 0x4000 | n << 8; shlr = lambda n: 0x4001 | n << 8
shll2 = lambda n: 0x4008 | n << 8; shlr2 = lambda n: 0x4009 | n << 8
shll8 = lambda n: 0x4018 | n << 8; shlr8 = lambda n: 0x4019 | n << 8
shll16 = lambda n: 0x4028 | n << 8; shlr16 = lambda n: 0x4029 | n << 8
dt = lambda n: 0x4010 | n << 8
ldw_r0 = lambda m, n: 0x000D | n << 8 | m << 4
push = lambda m: 0x2F06 | m << 4; pop = lambda n: 0x60F6 | n << 8


def data_part():
    data = bytearray(); lab = {}
    def put(name, b):
        nonlocal data
        data += bytes(-len(data) % 4); lab[name] = P.DATA + len(data); data += b
    put('cur', bytes(4))
    put('ron', b''.join(struct.pack('>HH', *x) for x in P.REGS_ON) + b'\xff\xff')
    put('roff', b''.join(struct.pack('>HH', *x) for x in P.REGS_OFF) + b'\xff\xff')
    pal = [0] * 16; pal[1] = 0x8000; pal[15] = 0xFFFF
    put('pal', struct.pack('>16H', *pal))
    put('etab', b''.join(struct.pack('>H', sum(((n >> (3 - i)) & 1) << (12 - 4 * i) for i in range(4))) for n in range(16)))
    assert P.DATA + len(data) <= BUF
    return bytes(data), lab


def assemble():
    data, dlab = data_part()
    a = A(P.RES); a.lab.update(dlab); W = a.w
    # ---- VBI 감싸개 ----
    a.L('vbi'); W(0x4F22); a.ld(0, P.VBI); W(0x400B, 0x0009)
    a.br('bsr', 'sub'); W(0x0009)
    W(0x4F26, 0x000B, 0x0009)
    # ---- 머리 훅(memcpy 대신: r4 = 0x06030B70, r5 = 머리, r6 = 0x80) — r4‥r6·PR 보존, 원래 memcpy 로 ----
    a.L('hdr')
    a.ld(1, SUBBUF); W(movi(0, 0), 0x2102)               # 묶음 무효
    W(0x8553, exw(0, 3), movi(2, 0x30), 0x3326); a.br('bf', 'hd')   # r3 = 데이터 시작 > 0x30 ?
    W(mov(5, 7), addi(7, 0x30), 0x6072); a.ld(2, 0x44535542); W(0x3020); a.br('bf', 'hd')   # @r7 == 'DSUB'
    W(addi(3, -0x30)); a.ld(2, SUBMAX); W(0x3326); a.br('bt', 'hd')  # 길이 > SUBMAX → 안 실음
    W(shlr2(3))
    a.L('hc'); W(0x6076, 0x2102, addi(1, 4), dt(3)); a.br('bf', 'hc')
    a.L('hd'); a.ld(0, MEMCPY); W(0x402B, 0x0009)
    # ---- sub(VBI 뒤) ----
    a.L('sub'); W(0x4F22)
    a.ld(1, SUBBUF); W(0x6012); a.ld(2, 0x44535542); W(0x3020); a.br('bf', 'none')
    a.ld(1, STREAMING); W(0x6012, 0x2008); a.br('bt', 'none')        # ★스트림 재생 중일 때만(타이틀에서 오프닝 자막 남음 — 사용자 2026-10-10)
    a.ld(1, P.CLOCK); W(0x6312)                                       # r3 = 시각
    a.ld(4, SUBBUF); W(0x8542, exw(0, 6)); W(mov(4, 1), addi(1, 16))  # r6 = 쪽 수(+4) · r1 = 쪽 표
    W(0x2668); a.br('bt', 'none')
    a.L('lp'); W(0x6015, exw(0, 0), 0x3303); a.br('bf', 'nx')         # t0 ≤ 시각 (r1 → t1)
    W(0x6011, exw(0, 0), 0x3037); a.br('bf', 'nx')                    # t1 > 시각
    W(0x8511, exw(0, 5), ADD(4, 5)); a.br('bra', 'have'); W(0x0009)   # r5 = SUBBUF + 쪽 자리
    a.L('nx'); W(addi(1, 6), dt(6)); a.br('bf', 'lp')                 # 다음 칸(8 B 중 2 B 읽음)
    a.L('none'); W(movi(5, 0))
    a.L('have'); a.ld(1, 'cur'); W(0x6012, 0x3050); a.br('bt', 'same')
    W(0x2152, 0x2558); a.br('bt', 'off')
    a.br('bsr', 'draw'); W(mov(5, 1))                                 # 지연 칸: r1 = 쪽
    a.br('bra', 'on'); W(0x0009)
    a.L('same'); W(0x2558); a.br('bt', 'ret')
    a.L('on'); a.ld(1, 'ron'); a.br('bsr', 'wregs'); W(0x0009)
    a.ld(1, 'pal'); a.ld(2, P.PALV); W(0xE308)
    a.L('pl'); W(0x6016, 0x2202, 0x7204, 0x4310); a.br('bf', 'pl')
    a.br('bra', 'ret'); W(0x0009)
    a.L('off'); a.ld(1, 'roff'); a.br('bsr', 'wregs'); W(0x0009)
    a.L('ret'); W(0x4F26, 0x000B, 0x0009)
    # ---- wregs ----
    a.L('wregs'); a.ld(2, P.VDP2)
    a.L('wl'); W(0x6015, 0x4011); a.br('bf', 'wd')
    W(0x6303, 0x332C, 0x6015, 0x2301); a.br('bra', 'wl'); W(0x0009)
    a.L('wd'); W(0x000B, 0x0009)
    # ---- draw(r1 = 쪽) — 버닝 레인저 draw 를 옮김 ----
    a.L('draw')
    W(0x4F22, push(1)); W(*[push(r) for r in range(8, 15)])
    a.ld(1, P.MAPV); a.ld(2, P.BLANK << 16 | P.BLANK); a.ld(3, 28 * 64 * 2 // 4)
    a.L('mf'); W(0x2122, 0x7104, 0x4310); a.br('bf', 'mf')            # 지도 0‥27행 빈칸
    W(0x58F7)                                                         # r8 = 쪽
    a.ld(2, BUF); a.ld(3, BSTR * 34 // 4); W(movi(0, 0))
    a.L('cb'); W(0x2202, addi(2, 4), dt(3)); a.br('bf', 'cb')
    a.ld(9, SUBBUF); W(0x8596, exw(0, 0), ADD(0, 9))                  # r9 = 글꼴
    W(ldb0(8, 3), exb(0, 10), mov(8, 11), addi(11, 4))
    W(0x2AA8); a.br('bt', 'chd')
    a.L('ch')
    W(ldbp(11, 0), exb(0, 1), shll(1), mov(1, 12), shll2(12), shll(12), ADD(1, 12), ADD(9, 12))
    W(ldbp(11, 0), exb(0, 13))
    W(ldbp(11, 0), exb(0, 0), mov(0, 2), 0xC804); a.br('bt', 'g8')     # tst #4 — 글자 번호 9번째 비트
    a.ld(1, 256 * 18); W(ADD(1, 12))
    a.L('g8')
    W(0xC901, shll8(0), OR(0, 13), addi(13, 8), shlr(2), mov(2, 0), 0xC901, mov(0, 2))   # r2 = 줄(비트 1)
    W(shll2(2), shll2(2), addi(2, 4), movi(3, BSTR), 0x0237, 0x021A)
    a.ld(3, BUF); W(ADD(3, 2), mov(13, 0), shlr2(0), shlr(0), ADD(0, 2))
    W(mov(13, 0), 0xC907, mov(0, 14), movi(3, 6))
    a.L('gp')
    W(ldbp(12, 4), exb(4, 4), ldbp(12, 5), exb(5, 5), ldbp(12, 6), exb(6, 6))
    W(mov(4, 0), shll2(0), shll2(0), mov(5, 1), shlr2(1), shlr2(1))
    a.br('bsr', 'stamp'); W(OR(1, 0))
    W(mov(5, 0), 0xC90F, shll8(0))
    a.br('bsr', 'stamp'); W(OR(6, 0))
    W(dt(3)); a.br('bf', 'gp')
    W(dt(10)); a.br('bf', 'ch')
    a.L('chd')
    W(ldb0(8, 1), exb(0, 9))
    a.ld(10, BUF); W(addi(10, BSTR)); a.ld(11, P.CELLV); a.ld(12, 'etab')
    a.L('cy'); W(ldb0(8, 0), exb(0, 13), mov(10, 14))
    a.L('cx'); W(mov(14, 2), movi(3, 8))
    a.L('cyy')
    W(mov(2, 4), addi(4, -BSTR), mov(2, 5), addi(5, BSTR))
    W(ldb(4, 0), ldb(2, 1), OR(1, 0), ldb(5, 1), OR(1, 0), exb(0, 6), shll8(6))
    W(ldb0(4, 1), mov(0, 1), ldb0(2, 1), OR(0, 1), ldb0(5, 1), OR(1, 0), exb(0, 0), OR(0, 6), shll8(6))
    W(ldb0(4, 2), mov(0, 1), ldb0(2, 2), OR(0, 1), ldb0(5, 2), OR(1, 0), exb(0, 0), OR(0, 6))
    W(mov(6, 1), shlr8(1), mov(6, 0), shll(0), shlr8(0), OR(0, 1), mov(6, 0), shlr(0), shlr8(0), OR(0, 1))
    W(ldb0(2, 1), exb(0, 7), 0x6077, AND(0, 1), exb(1, 1))
    W(mov(7, 0), shlr2(0), shlr2(0), ADD(0, 0), ldw_r0(12, 4), exw(4, 4), shll16(4))
    W(mov(7, 0), 0xC90F, ADD(0, 0), ldw_r0(12, 0), exw(0, 0), OR(0, 4))
    W(mov(4, 0), shll(0), OR(0, 4), mov(4, 0), shll2(0), OR(0, 4))
    W(mov(1, 0), shlr2(0), shlr2(0), ADD(0, 0), ldw_r0(12, 5), exw(5, 5), shll16(5))
    W(mov(1, 0), 0xC90F, ADD(0, 0), ldw_r0(12, 0), exw(0, 0), OR(0, 5), OR(5, 4))
    W(0x2B42, addi(11, 4), addi(2, BSTR), dt(3)); a.br('bf', 'cyy')
    W(addi(14, 1), dt(13)); a.br('bf', 'cx')
    W(movi(0, BSTR * 2), shll2(0), ADD(0, 10), dt(9)); a.br('bf', 'cy')
    W(*[pop(r) for r in range(14, 7, -1)]); W(pop(1))
    # 지도: 아래(27−nrow 행)부터, 열 c0
    W(0x8410, 0x600C, 0x6703)                                         # r7 = w8
    W(0x8412, 0x600C, 0x6303, 0x4300)                                 # r3 = c0*2
    W(0x8411, 0x600C, 0x6503)                                         # r5 = nrow
    a.ld(2, P.MAPV + 27 * 128); W(0x323C, mov(5, 0), shll8(0), shlr(0), 0x3208)   # r2 = 지도 + 27*128 + c0*2 − nrow*128
    a.ld(4, P.FIRST)
    a.L('row'); W(0x6023, 0x6673)
    a.L('col'); W(0x2041, 0x7002, 0x7401, 0x4610); a.br('bf', 'col')
    a.ld(0, 128); W(0x320C, 0x4510); a.br('bf', 'row')
    W(0x4F26, 0x000B, 0x0009)
    # ---- stamp ----
    a.L('stamp')
    W(shll8(0), shll2(0), shll2(0), mov(14, 1), 0x2118); a.br('bt', 'sd')
    a.L('sl'); W(shlr(0), dt(1)); a.br('bf', 'sl')
    a.L('sd'); W(mov(0, 7), shlr16(0), ldb(2, 1), OR(1, 0), stb(0, 2))
    W(mov(7, 1), shlr8(1), ldb0(2, 1), OR(1, 0), stb0(2, 1))
    W(ldb0(2, 2), OR(7, 0), stb0(2, 2), 0x000B, addi(2, BSTR))
    code = a.build(); assert len(code) <= P.DATA - P.RES, len(code)
    return code + bytes(P.DATA - P.RES - len(code)) + data, a.lab


def build_exe():
    exe = bytearray(open(P.EXE, 'rb').read()); assert len(exe) == P.BSS - P.LOAD
    res, lab = assemble(); res += bytes(-len(res) % 4)
    st = P.stub(len(res) // 4)
    for lit, old, new in ((P.ENTRY_LIT, P.MAIN, P.BSS), (P.VBI_LIT, P.VBI, lab['vbi']), (MEMCPY_LIT, MEMCPY, lab['hdr'])):
        assert struct.unpack_from('>I', exe, lit - P.LOAD)[0] == old; struct.pack_into('>I', exe, lit - P.LOAD, new)
    return bytes(exe) + st + res, res, lab


# ============ 검산 ============
def check(new, res, lab, st2b, pay, delay):
    ok = True
    m = S.Mem(); m.add(0x06000000, 0x100000); m.add(0x05E00000, 0x80000); m.add(0x05F00000, 0x1000); m.add(0x05F80000, 0x200)
    m._f(P.LOAD)[0][0x10000:0x10000 + len(new)] = new
    S.run(m, P.BSS, stop=P.MAIN)
    got = bytes(m.r8(P.RES + i) for i in range(len(res))); ok &= got == res
    print('① 복사 토막 %s' % (got == res))
    # ② 머리 훅: 고리 버퍼 0x06058000 에 ST2 앞부분
    m._f(0x06058000)[0][0x58000:0x58000 + 0x8000] = st2b[:0x8000]
    seen = []
    S.run(m, lab['hdr'], regs=[0, 0, 0, 0, 0x06030B70, 0x06058000, 0x80, 0], calls={MEMCPY: lambda r, mm: seen.append(r[4:7])})
    gp = bytes(m.r8(SUBBUF + i) for i in range(len(pay)))
    g2 = seen and seen[0] == [0x06030B70, 0x06058000, 0x80]
    print('② 머리 훅: 묶음 %d B 복사 %s · memcpy 인수 보존 %s' % (len(pay), gp == pay, g2)); ok &= gp == pay and bool(g2)
    # ③ 쪽 고르기·그리기
    m.w32(STREAMING, 1)
    for v, want in ((P.PAGES[0][0] + delay + 10, 0), (P.PAGES[1][0] + delay + 5, 1), (P.PAGES[1][1] + delay + 5, None)):
        m.w32(P.CLOCK, v)
        S.run(m, lab['vbi'], calls={P.VBI: lambda r, mm: None})
        if want is None:
            g = m.r16(P.VDP2 + 0x20) == 0x0007; print('  시각 %d → 없음 %s' % (v, g)); ok &= g; continue
        w8, nrow, chars = G.layout(P.PAGES[want][2]); ref = G.cells_4bpp(G.reference(w8, nrow, chars), w8, nrow)
        gc = bytes(m.r8(P.CELLV + i) for i in range(len(ref)))
        row0 = 27 - nrow; c0 = (40 - w8) // 2
        exp = [P.BLANK] * (28 * 64)
        for y in range(nrow):
            for x in range(w8): exp[(row0 + y) * 64 + c0 + x] = P.FIRST + y * w8 + x
        mp = [m.r16(P.MAPV + 2 * i) for i in range(28 * 64)]
        regs = all(m.r16(P.VDP2 + o) == val for o, val in P.REGS_ON)
        g = gc == ref and mp == exp and regs
        print('  시각 %d → 쪽 %d 셀 %s 지도 %s 레지스터 %s' % (v, want, gc == ref, mp == exp, regs)); ok &= g
    # ③-2 재생 중 아님(타이틀) → 자막 끔
    m.w32(P.CLOCK, P.PAGES[0][0] + delay + 10); S.run(m, lab['vbi'], calls={P.VBI: lambda r, mm: None})
    m.w32(STREAMING, 0); S.run(m, lab['vbi'], calls={P.VBI: lambda r, mm: None})
    g = m.r16(P.VDP2 + 0x20) == 0x0007; print('③-2 재생 중 아님 → 자막 끔 %s' % g); ok &= g
    # ④ 'DSUB' 없는 음성 → 묶음 무효
    m._f(0x06058000)[0][0x58000:0x58000 + 0x100] = open(os.path.join(ROOT, 'work', 'disc', 'S00200.ST2'), 'rb').read()[:0x100]
    S.run(m, lab['hdr'], regs=[0, 0, 0, 0, 0x06030B70, 0x06058000, 0x80, 0], calls={MEMCPY: lambda r, mm: None})
    g = m.r32(SUBBUF) == 0; print('④ 자막 없는 음성 → 묶음 무효 %s' % g); ok &= g
    return ok


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    orig = disc.read(VOICE)
    pay = payload(P.PAGES, 0)
    _, head = st2(orig, pay); delay = round(head / 735)
    pay = payload(P.PAGES, delay); st2b, head2 = st2(orig, pay); assert head2 == head
    new, res, lab = build_exe()
    print('BLDANIM %d B · 몸 %d B · 묶음 %d B + 채움 %d B → 머리 %d B(무음 %d프레임 보정) · S00100 %d → %d B'
          % (len(new), len(res), len(pay), FILL, head, delay, len(orig), len(st2b)))
    if not check(new, res, lab, st2b, pay, delay):
        raise SystemExit('검산 실패')
    if '--write' in sys.argv:
        iso.patch(OUT, {'/BLDANIM.BIN': new, VOICE: st2b})


if __name__ == '__main__':
    main()
