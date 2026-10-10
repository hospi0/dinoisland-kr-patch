# -*- coding: utf-8 -*-
r"""다이노 아일랜드 자막 훅 — VDP1 스프라이트판 (2026-10-10)
  ★VDP2 NBG3 판은 장면에 따라 다른 층 표시를 망가뜨림(오프닝·대사 «점만 남음», B1 주기 두 배치 모두) → VDP2 는 하나도 안 건드린다.
  · 머리 훅·쪽 고르기 = poc2 와 같음(ST2 머리 DSUB → SUBBUF, 스트림 재생 중 0x06031CD0 일 때만, 시각 0x06046E74).
  · 그림: 쪽을 1비트 버퍼에 찍고(버닝 레인저 stamp) → 8비트 선형 그림(0 투명 · 0xFE 검정 테두리 · 0xFF 흰 글자)을 VDP1 VRAM 0x7A000 에
    (0x7A000‥0x7FFFF 는 스테이트 15개 모두 초기 쓰레기 무늬 = 안 씀).
  · 명령: 확대 스프라이트(종류 1 — 게임 VBI 의 명령표 순회 0x06017D26 은 종류 0 만 좌표를 고침) PMOD 0x00A0(8비트 256색)·COLR 0x8400(선택지 말풍선과 같은 묶음
    → 스프라이트 우선순위 6) · SRCA 0x7A000/8 · 아래 가운데. 매 VBI 뒤 명령표(0x25C00000)를 END 까지 훑어 END 자리에 넣고 뒤에 END. 꺼지면 END 로 되돌림.
  · 색: CRAM 0x7FE = 검정, 0x7FF = 흰색(스프라이트 색 0x84FE/0x84FF + CRAOFB 스프라이트 0x300) — 팔레트 127, 모든 스테이트 빈 칸.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sh2asm import A
import poc as P, poc2 as Q
from poc2 import (mov, ldb, ldbp, stb, ldb0, stb0, exb, exw, OR, AND, ADD, addi, movi, shll, shlr, shll2, shlr2,
                  shll8, shlr8, shll16, shlr16, dt, push, pop)

TEX = 0x25C7A000; TEXA = (TEX & 0x7FFFF) // 8
LIST = 0x25C00000
CRAM_BK = 0x25F00000 + 0x7FE * 2
BUF = Q.BUF; BSTR = Q.BSTR; SUBBUF = Q.SUBBUF


def data_part():
    data = bytearray(); lab = {}
    def put(name, b):
        nonlocal data
        data += bytes(-len(data) % 4); lab[name] = P.DATA + len(data); data += b
    put('cur', bytes(4))
    put('cmd', struct.pack('>16H', 0x0001, 0, 0x00A0, 0x8400, TEXA, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    assert P.DATA + len(data) <= BUF
    return bytes(data), lab


def assemble():
    data, dlab = data_part()
    a = A(P.RES); a.lab.update(dlab); W = a.w
    # ---- VBI 감싸개 ----
    a.L('vbi'); W(0x4F22); a.ld(0, P.VBI); W(0x400B, 0x0009)
    a.br('bsr', 'sub'); W(0x0009)
    W(0x4F26, 0x000B, 0x0009)
    # ---- 머리 훅(poc2 와 같음) ----
    a.L('hdr')
    a.ld(1, SUBBUF); W(movi(0, 0), 0x2102)
    W(0x8553, exw(0, 3), movi(2, 0x30), 0x3326); a.br('bf', 'hd')
    W(mov(5, 7), addi(7, 0x30), 0x6072); a.ld(2, 0x44535542); W(0x3020); a.br('bf', 'hd')
    W(addi(3, -0x30)); a.ld(2, Q.SUBMAX); W(0x3326); a.br('bt', 'hd')
    W(shlr2(3))
    a.L('hc'); W(0x6076, 0x2102, addi(1, 4), dt(3)); a.br('bf', 'hc')
    a.L('hd'); a.ld(0, Q.MEMCPY); W(0x402B, 0x0009)
    # ---- sub ----
    a.L('sub'); W(0x4F22)
    a.ld(1, SUBBUF); W(0x6012); a.ld(2, 0x44535542); W(0x3020); a.br('bf', 'none')
    a.ld(1, Q.STREAMING); W(0x6012, 0x2008); a.br('bt', 'none')
    a.ld(1, P.CLOCK); W(0x6312)
    a.ld(4, SUBBUF); W(0x8542, exw(0, 6)); W(mov(4, 1), addi(1, 16))
    W(0x2668); a.br('bt', 'none')
    a.L('lp'); W(0x6015, exw(0, 0), 0x3303); a.br('bf', 'nx')
    W(0x6011, exw(0, 0), 0x3037); a.br('bf', 'nx')
    W(0x8511, exw(0, 5), ADD(4, 5)); a.br('bra', 'have'); W(0x0009)
    a.L('nx'); W(addi(1, 6), dt(6)); a.br('bf', 'lp')
    a.L('none'); W(movi(5, 0))
    a.L('have'); a.ld(1, 'cur'); W(0x6012, 0x3050); a.br('bt', 'same')
    W(0x2152, 0x2558); a.br('bt', 'off')
    a.br('bsr', 'draw'); W(mov(5, 1))
    a.L('on')                                                          # 매 프레임: 색 + 명령 넣기
    a.ld(1, CRAM_BK); a.ld(0, 0x8000FFFF); W(0x2102)                  # 0x7FE 검정 · 0x7FF 흰색
    a.ld(1, LIST); a.ld(3, 512)
    a.L('il'); W(0x6011, exw(0, 0)); a.ld(2, 0x8000); W(0x3020); a.br('bt', 'iput')
    W(0x8801); a.br('bf', 'inx')                                      # 종류 1 이고 SRCA 가 우리 것이면 덮어씀
    W(0x8514, exw(0, 0)); a.ld(2, TEXA); W(0x3020); a.br('bt', 'iput')
    a.L('inx'); W(addi(1, 32), dt(3)); a.br('bf', 'il')
    a.br('bra', 'ret'); W(0x0009)
    a.L('iput'); a.ld(2, 'cmd'); W(movi(3, 8))
    a.L('ic'); W(0x6026, 0x2102, addi(1, 4), dt(3)); a.br('bf', 'ic')
    a.ld(0, 0x8000); W(0x2101)                                        # 뒤에 END
    a.br('bra', 'ret'); W(0x0009)
    a.L('same'); W(0x2558); a.br('bf', 'on')
    a.L('off')                                                         # 꺼짐: 우리 명령 자리를 END 로
    a.ld(1, LIST); a.ld(3, 512)
    a.L('rl'); W(0x6011, exw(0, 0)); a.ld(2, 0x8000); W(0x3020); a.br('bt', 'ret')
    W(0x8801); a.br('bf', 'rnx')
    W(0x8514, exw(0, 0)); a.ld(2, TEXA); W(0x3020); a.br('bf', 'rnx')
    a.ld(0, 0x8000); W(0x2101); a.br('bra', 'ret'); W(0x0009)
    a.L('rnx'); W(addi(1, 32), dt(3)); a.br('bf', 'rl')
    a.L('ret'); W(0x4F26, 0x000B, 0x0009)
    # ---- draw(r1 = 쪽): 1비트 버퍼에 찍기 → 8비트 선형 그림 → 명령 칸 ----
    a.L('draw')
    W(0x4F22, push(1)); W(*[push(r) for r in range(8, 15)])
    W(0x58F7)                                                          # r8 = 쪽
    a.ld(2, BUF); a.ld(3, BSTR * 34 // 4); W(movi(0, 0))
    a.L('cb'); W(0x2202, addi(2, 4), dt(3)); a.br('bf', 'cb')
    a.ld(9, SUBBUF); W(0x8596, exw(0, 0), ADD(0, 9))
    W(ldb0(8, 3), exb(0, 10), mov(8, 11), addi(11, 4))
    W(0x2AA8); a.br('bt', 'chd')
    a.L('ch')
    W(ldbp(11, 0), exb(0, 1), shll(1), mov(1, 12), shll2(12), shll(12), ADD(1, 12), ADD(9, 12))
    W(ldbp(11, 0), exb(0, 13))
    W(ldbp(11, 0), exb(0, 0), mov(0, 2), 0xC804); a.br('bt', 'g8')
    a.ld(1, 256 * 18); W(ADD(1, 12))
    a.L('g8')
    W(0xC901, shll8(0), OR(0, 13), addi(13, 8), shlr(2), mov(2, 0), 0xC901, mov(0, 2))
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
    # 8비트 선형: 행 y(nrow*8 개) × 열 cx(w8 개) × 8 화소
    W(ldb0(8, 1), exb(0, 9), shll2(9), shll(9))                       # r9 = 행 수
    a.ld(10, BUF); W(addi(10, BSTR)); a.ld(11, TEX)
    a.L('ry'); W(ldb0(8, 0), exb(0, 13), mov(10, 14))
    a.L('rx'); W(mov(14, 2))
    W(mov(2, 4), addi(4, -BSTR), mov(2, 5), addi(5, BSTR))
    W(ldb(4, 0), ldb(2, 1), OR(1, 0), ldb(5, 1), OR(1, 0), exb(0, 6), shll8(6))
    W(ldb0(4, 1), mov(0, 1), ldb0(2, 1), OR(0, 1), ldb0(5, 1), OR(1, 0), exb(0, 0), OR(0, 6), shll8(6))
    W(ldb0(4, 2), mov(0, 1), ldb0(2, 2), OR(0, 1), ldb0(5, 2), OR(1, 0), exb(0, 0), OR(0, 6))
    W(mov(6, 1), shlr8(1), mov(6, 0), shll(0), shlr8(0), OR(0, 1), mov(6, 0), shlr(0), shlr8(0), OR(0, 1))
    W(ldb0(2, 1), exb(0, 7), 0x6077, AND(0, 1), exb(1, 1))           # r7 = 글자 · r1 = 테두리
    W(movi(3, 8))
    a.L('eb'); W(mov(7, 0), 0xC880); a.br('bt', 'e1')
    W(movi(0, -1)); a.br('bra', 'es'); W(0x0009)
    a.L('e1'); W(mov(1, 0), 0xC880); a.br('bt', 'e0')
    W(movi(0, -2)); a.br('bra', 'es'); W(0x0009)
    a.L('e0'); W(movi(0, 0))
    a.L('es'); W(stb(0, 11), addi(11, 1), shll(7), shll(1), dt(3)); a.br('bf', 'eb')
    W(addi(14, 1), dt(13)); a.br('bf', 'rx')
    W(movi(0, BSTR), ADD(0, 10), dt(9)); a.br('bf', 'ry')
    W(*[pop(r) for r in range(14, 7, -1)]); W(pop(1))
    # 명령 칸: SIZE · XA YA · XC YC (아래 가운데, 바닥 8px 여유)
    W(ldb0(1, 0), exb(0, 7), ldb0(1, 1), exb(0, 5))                   # r7 = w8 · r5 = nrow
    a.ld(2, 'cmd')
    W(mov(7, 0), shll8(0), mov(5, 6), shll2(6), shll(6), OR(6, 0), 0x8125)          # SIZE = w8<<8 | nrow*8
    W(mov(7, 0), shll2(0), movi(6, 80), shll(6), 0x3608, mov(6, 0), 0x8126)          # XA = 160 − w8*4
    W(mov(7, 0), shll2(0), shll(0), ADD(6, 0), addi(0, -1), 0x812A)                  # XC = XA + w8*8 − 1
    W(mov(5, 0), shll2(0), shll(0)); a.ld(6, 216); W(0x3608, mov(6, 0), 0x8127)      # YA = 216 − nrow*8
    W(mov(5, 0), shll2(0), shll(0), ADD(6, 0), addi(0, -1), 0x812B)                  # YC = YA + nrow*8 − 1
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
    for lit, old, new in ((P.ENTRY_LIT, P.MAIN, P.BSS), (P.VBI_LIT, P.VBI, lab['vbi']), (Q.MEMCPY_LIT, Q.MEMCPY, lab['hdr'])):
        assert struct.unpack_from('>I', exe, lit - P.LOAD)[0] == old; struct.pack_into('>I', exe, lit - P.LOAD, new)
    return bytes(exe) + st + res, res, lab
