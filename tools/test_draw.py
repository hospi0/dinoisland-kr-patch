# -*- coding: utf-8 -*-
"""실제 묶음의 모든 쪽을 sh2sim 으로 그려 기준 그림(glyphpack.reference)과 비교 (2026-10-10)
   python tools/test_draw.py [음성 …]  (기본: 글자 많은 S16100·S17700)"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.append(r'C:\claude\project\burningrangers-kr-patch\tools')
import glyphpack as G
import build as B, poc as P, poc2 as Q, sh2sim as S


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    new, res, lab = Q.build_exe()
    vr = B.voice_rows(); ok = True
    for v in sys.argv[1:] or ['S16100', 'S17700']:
        pay, n, g = B.voice_payload(v, vr[v])
        pages = [(a, b, p) for a, b, p in B.pages_for(vr[v])]
        m = S.Mem(); m.add(0x06000000, 0x100000); m.add(0x05E00000, 0x80000); m.add(0x05F00000, 0x1000); m.add(0x05F80000, 0x200)
        m._f(P.RES)[0][P.RES - 0x06000000:P.RES - 0x06000000 + len(res)] = res
        m._f(Q.SUBBUF)[0][Q.SUBBUF - 0x06000000:Q.SUBBUF - 0x06000000 + len(pay)] = pay
        bad = 0
        for k, (_, _, lines) in enumerate(pages):
            off = struct.unpack_from('>H', pay, 16 + 8 * k + 4)[0]
            S.run(m, lab['draw'], regs=[0, Q.SUBBUF + off] + [0] * 13 + [0x060FF000])
            w8, nrow, chars = G.layout(lines)
            ref = G.cells_4bpp(G.reference(w8, nrow, chars), w8, nrow)
            got = bytes(m.r8(P.CELLV + i) for i in range(len(ref)))
            bad += got != ref
        print('%s 글자 %d · 쪽 %d · 그림 틀림 %d' % (v, g, n, bad)); ok &= bad == 0
    print('결과', '통과' if ok else '실패')


if __name__ == '__main__':
    main()
