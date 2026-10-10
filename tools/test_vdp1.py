# -*- coding: utf-8 -*-
"""VDP1 자막 훅 검산(2026-10-10): 명령 넣기·그림·끄기·VDP2 안 건드림 + 실제 큰 음성 전 쪽 그림"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.append(r'C:\claude\project\burningrangers-kr-patch\tools')
import glyphpack as G
import build as B, poc as P, poc2 as Q, hook as H, sh2sim as S


def mem(res):
    m = S.Mem(); m.add(0x06000000, 0x100000); m.add(0x05C00000, 0x80000); m.add(0x05F00000, 0x1000); m.add(0x05F80000, 0x200)
    m._f(P.RES)[0][P.RES - 0x06000000:P.RES - 0x06000000 + len(res)] = res
    return m


def ref_tex(lines):
    w8, nrow, chars = G.layout(lines); px = G.reference(w8, nrow, chars)
    return w8, nrow, bytes({0: 0, 1: 0xFE, 15: 0xFF}[int(v)] for v in px.ravel())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    new, res, lab = H.build_exe(); ok = True
    vr = B.voice_rows(); v = 'S00100'
    pay, n, g = B.voice_payload(v, vr[v]); pages = B.pages_for(vr[v])
    for listlen in (0, 3):
        m = mem(res); m._f(Q.SUBBUF)[0][Q.SUBBUF - 0x06000000:Q.SUBBUF - 0x06000000 + len(pay)] = pay
        for k in range(listlen): m.w16(H.LIST + 32 * k, 0x0000); m.w16(H.LIST + 32 * k + 8, 0x1234)
        m.w16(H.LIST + 32 * listlen, 0x8000); m.w16(H.LIST + 32 * listlen + 32, 0x1234)   # END 다음 칸 = 게임이 짓는 중인 명령(건드리면 안 됨)
        regs0 = bytes(m.r8(0x05F80000 + i) for i in range(0x120))
        m.w32(Q.STREAMING, 1)
        t0 = struct.unpack_from('>H', pay, 16)[0]
        m.w32(H.FEED, (t0 + 2 + H.LEAD) * 735 + 1)
        S.run(m, lab['vbi'], calls={P.VBI: lambda r, mm: None})
        X = H.LIST + 32 * listlen
        O = H.OWN; cmd = [m.r16(O + 2 * i) for i in range(16)]
        w8, nrow, tex = ref_tex(pages[0][2])
        got = bytes(m.r8(H.TEX + i) for i in range(len(tex)))
        want_cmd = [1, 0, 0xA0, 0x8400, H.TEXA, w8 << 8 | nrow * 8, 160 - w8 * 4, 216 - nrow * 8, 0, 0,
                    160 - w8 * 4 + w8 * 8 - 1, 216 - 1, 0, 0, 0, 0]
        c1 = cmd == want_cmd and m.r16(X) == 0x5000 and m.r16(X + 2) == H.OWNL
        c2 = m.r16(O + 32) == 0x8000 and m.r16(X + 32) == 0x1234; c3 = got == tex
        c4 = bytes(m.r8(0x05F80000 + i) for i in range(0x120)) == regs0
        c5 = m.r16(0x05F00FFC) == 0x0000 and m.r16(0x05F00FFE) == 0x7FFF
        games = all(m.r16(H.LIST + 32 * k) == 0 and m.r16(H.LIST + 32 * k + 8) == 0x1234 for k in range(listlen))
        print('게임 명령 %d개: 자막 명령·점프 %s · 우리 END·다음 칸 그대로 %s · 그림 %s · VDP2 안 건드림 %s · 색 %s · 게임 명령 그대로 %s' % (listlen, c1, c2, c3, c4, c5, games))
        if not c1: print('  ', [hex(x) for x in cmd], [hex(x) for x in want_cmd])
        S.run(m, lab['vbi'], calls={P.VBI: lambda r, mm: None})      # 두 번째 프레임: 같은 자리 다시
        c6 = m.r16(X) == 0x5000 and m.r16(O + 32) == 0x8000 and m.r16(X + 32) == 0x1234
        m.w32(Q.STREAMING, 0); S.run(m, lab['vbi'], calls={P.VBI: lambda r, mm: None})
        c7 = m.r16(X) == 0x8000
        print('  두 번째 프레임 그대로 %s · 꺼지면 END 로 %s' % (c6, c7)); ok &= all((c1, c2, c3, c4, c5, games, c6, c7))
    # 시계 = 넘긴 바이트 위치 ÷ 735 − 앞섬 + 센 프레임 · 일시정지(CD0 = 0) 면 꺼짐
    v = 'S00100'; pay, n, g = B.voice_payload(v, vr[v]); pages = B.pages_for(vr[v])
    T = lambda k, o: struct.unpack_from('>H', pay, 16 + 8 * k + o)[0]
    for t in (2817, 5533, 0):
        m = mem(res); m._f(Q.SUBBUF)[0][Q.SUBBUF - 0x06000000:Q.SUBBUF - 0x06000000 + len(pay)] = pay
        m.w16(H.LIST, 0x8000); m.w32(Q.STREAMING, 1); m.w32(H.FEED, (t + H.LEAD) * 735 + 1 if t else 0)
        S.run(m, lab['vbi'], calls={P.VBI: lambda r, mm: None})
        want = [p for k, p in enumerate(pages) if t and T(k, 0) <= t < T(k, 2)]
        if want:
            w8, nrow, tex = ref_tex(want[0][2]); hit = bytes(m.r8(H.TEX + i) for i in range(len(tex))) == tex and m.r16(H.LIST) == 0x5000
        else:
            hit = m.r16(H.LIST) == 0x8000
        print('  시계 %d프레임 %s %s' % (t, want[0][2] if want else '(자막 없음)', hit)); ok &= hit
    # 게임이 표를 읽기 전에 우리 점프를 치우는지(END 찾기 대체 fe)
    m = mem(res); m.w16(H.LIST, 0x5000); m.w16(H.LIST + 2, H.OWNL); m.w16(H.LIST + 32, 0x1234); m.w16(H.LIST + 64, 0x8000)
    r, _ = S.run(m, lab['fe'], regs=[0, 0, 0, 0x77, H.LIST] + [0] * 10 + [0x060FF000])
    hit = r[0] == H.LIST and m.r16(H.LIST) == 0x8000 and r[3] == 0x77 and r[4] == H.LIST
    print('  END 찾기 전 점프 치움 %s' % hit); ok &= hit
    # 큰 음성 전 쪽 그림
    for v in ('S16100', 'S17700'):
        pay, n, g = B.voice_payload(v, vr[v]); pages = B.pages_for(vr[v])
        m = mem(res); m._f(Q.SUBBUF)[0][Q.SUBBUF - 0x06000000:Q.SUBBUF - 0x06000000 + len(pay)] = pay
        bad = 0
        for k, (_, _, lines) in enumerate(pages):
            off = struct.unpack_from('>H', pay, 16 + 8 * k + 4)[0]
            S.run(m, lab['draw'], regs=[0, Q.SUBBUF + off] + [0] * 13 + [0x060FF000])
            w8, nrow, tex = ref_tex(lines)
            bad += bytes(m.r8(H.TEX + i) for i in range(len(tex))) != tex
        print('%s 글자 %d · 쪽 %d · 그림 틀림 %d' % (v, g, n, bad)); ok &= bad == 0
    print('결과', '통과' if ok else '실패')


if __name__ == '__main__':
    main()
