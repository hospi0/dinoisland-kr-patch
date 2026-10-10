# -*- coding: utf-8 -*-
r"""GI 압축 두 가지(2026-10-10) — 게임 해제기를 SH-2 디스어셈으로 옮긴 파이썬판 + 압축기.
  지도(0x06019078, u16 출력): 바이트 b
     b&0x80        → 상위 바이트 = b (다음 명령)
     b>>4 = 0      → 낱말 n=(b&15)+1 개: 바이트마다 (상위|바이트)
     b>>4 = 1      → b&15 = 0 이면 끝, 아니면 시작 바이트 x 읽고 n=(b&15)+1 개 증가(x, x+1, … 바이트 안에서 돎)
     b>>4 = 2      → 앞 증가를 이어서 n 개
     b>>4 = 3      → x 읽어 기록[i] 에 넣고(i = 0‥3 돌림) n=(b&15)+2 개 반복
     b>>4 = 4‥7    → 기록[(b>>4)−4] 를 n=(b&15)+2 개 반복
  셀(0x06018ECC, 바이트 출력): b>>6 으로 갈림
     0: s=(b>>3)&7, c=b&7 — s=0 이면 x 읽어 기록B 에(1‥7 돌림), 아니면 x = 기록B[s]
        c≠0 이면 R12 = x · c=7 이면 다음 바이트 e(0 = 끝)로 개수 e+2, 아니면 c+2 개 x
     1: 두 색 무늬 5화소(비트 5 = 0 이면 색 두 개 새로 읽음) — 압축기는 안 씀
     2: k=(b>>2)&15, l=b&3 — k=0: 날 바이트 l+1 개(기록A 에) · k=8: 8바이트 앞을 l+5 개 복사 ·
        k&8: 기록B[k&7‥] l+1 개 · 그 밖: 기록A[k&7‥] l+1 개
     3: s=(b>>3)&7 — s=0 이면 x 읽어 기록A 에, 아니면 x = 기록A[s] · x 쓰고 R12 를 c+1 개(c=7 이면 e+1, e=0 끝)
     (기록 A·B 는 8칸, 쓰는 자리는 1‥7 돌림 — 0 번 칸은 늘 0, 그래서 s≠0 은 1‥7 칸)
"""
import struct


def dec_map(d, n_words):
    out = []; i = 0; hi = 0; hist = [0] * 4; hp = 0; inc = 0
    while True:
        b = d[i]; i += 1
        if b & 0x80:
            hi = b << 8; continue
        t, c = b >> 4, b & 15
        if t == 0:
            for _ in range(c + 1): out.append(hi | d[i]); i += 1
        elif t in (1, 2):
            if t == 1:
                if c == 0: return out, i
                inc = d[i]; i += 1
            for _ in range(c + 1): out.append(hi | (inc & 0xFF)); inc = (inc & 0xFF) + 1
        elif t == 3:
            x = d[i]; i += 1; hist[hp] = x; hp = (hp + 1) & 3
            out += [hi | x] * (c + 2)
        else:
            out += [hi | hist[t - 4]] * (c + 2)


def enc_map(words):
    """상위 바이트는 0x80 이상만(게임 지도와 같음 — 비트 15 는 표시와 무관). 증가 런·반복·날 낱말"""
    o = bytearray(); hi = None; i = 0; n = len(words)
    lit = []
    def flush():
        nonlocal lit
        while lit:
            k = lit[:16]; lit = lit[16:]
            o.append(0x00 | (len(k) - 1)); o.extend(k)
    while i < n:
        w = words[i] | 0x8000; h = w >> 8
        if h != hi:
            flush(); o.append(h); hi = h
        # 같은 상위 바이트 안에서만
        j = i
        while j < n and (words[j] | 0x8000) >> 8 == h: j += 1
        lo = [x & 0xFF for x in words[i:j]]
        k = 0
        while k < len(lo):
            r = 1
            while k + r < len(lo) and lo[k + r] == lo[k] and r < 17: r += 1
            s = 1
            while k + s < len(lo) and lo[k + s] == (lo[k] + s) & 0xFF and s < 16: s += 1
            if r >= 3:
                flush(); o.append(0x30 | (r - 2)); o.append(lo[k]); k += r
            elif s >= 3:
                flush(); o.append(0x10 | (s - 1)); o.append(lo[k]); k += s
            else:
                lit.append(lo[k]); k += 1
        flush(); i = j
    o.append(0x10)
    return bytes(o)


def dec_cells(d):
    out = bytearray(); i = 0; A = [0] * 8; B = [0] * 8; pa = 1; pb = 1; r12 = 0; c2 = [0, 0]
    while True:
        b = d[i]; i += 1
        t = b >> 6; s = (b >> 3) & 7; c = b & 7
        if t == 0:
            if s == 0:
                x = d[i]; i += 1; B[pb] = x; pb = pb + 1 if pb < 7 else 1
            else:
                x = B[s]                                 # MOV.B @(R0,R10) — s 번 칸
            if c != 0: r12 = x
            if c == 7:
                e = d[i]; i += 1
                if e == 0: return bytes(out), i
                cnt = e + 2
            else:
                cnt = c + 2
            out += bytes([x]) * cnt
        elif t == 1:
            if not b & 0x20:
                c2 = [d[i], d[i + 1]]; i += 2
            v = b
            for _ in range(5):
                out.append(c2[1] if v & 0x10 else c2[0]); v <<= 1
        elif t == 2:
            l = b & 3; k = (b >> 2) & 15
            if k == 0:
                for _ in range(l + 1):
                    x = d[i]; i += 1; A[pa] = x; pa = pa + 1 if pa < 7 else 1; out.append(x)
            elif k == 8:
                for _ in range(l + 5): out.append(out[-8])
            else:
                H = B if k & 8 else A; j = k & 7
                for _ in range(l + 1):
                    out.append(H[j]); j = j + 1 if j < 7 else 1
        else:
            if s == 0:
                x = d[i]; i += 1; A[pa] = x; pa = pa + 1 if pa < 7 else 1
            else:
                x = A[s]                                 # MOV.B @(R0,R14) — s 번 칸
            out.append(x)
            if c == 7:
                e = d[i]; i += 1
                if e == 0: return bytes(out), i
                cnt = e + 1
            else:
                cnt = c + 1
            out += bytes([r12]) * cnt


def enc_cells(data):
    """쓰는 명령: 0 런(00 sss≠0) · 같은 바이트 런(00 000 ccc x) · 8바이트 앞 복사(0xA0|l, 5‥8) · 날 바이트(0x80|l, 1‥4) · 끝 0x0F 00"""
    o = bytearray(); i = 0; n = len(data); lit = []
    def flush():
        nonlocal lit
        while lit:
            k = lit[:4]; lit = lit[4:]
            o.append(0x80 | (len(k) - 1)); o.extend(k)
    while i < n:
        x = data[i]
        r = 1
        while i + r < n and data[i + r] == x and r < 257: r += 1
        m = 0
        if i >= 8:
            while i + m < n and data[i + m] == data[i + m - 8] and m < 8: m += 1
        if r >= 2 and r >= m:
            flush()
            if r <= 8:
                o.append((0x08 if x == 0 else 0x00) | (r - 2))
            else:
                o.append((0x08 if x == 0 else 0x00) | 7)
            if x != 0: o.append(x)
            if r > 8: o.append(r - 2)
            i += r
        elif m >= 5:
            flush(); o.append(0xA0 | (m - 5)); i += m
        else:
            lit.append(x); i += 1
    flush(); o += b'\x0F\x00'
    return bytes(o)


def enc_cells2(data):
    """해제기 상태를 따라가는 탐욕 압축 — 자리마다 (덮는 바이트/드는 바이트) 가 가장 큰 명령"""
    o = bytearray(); i = 0; n = len(data)
    A = [0] * 8; B = [0] * 8; st = {'pa': 1, 'pb': 1, 'r12': 0, 'c2': None}
    def push(H, key, x):
        H[st[key]] = x; st[key] = st[key] + 1 if st[key] < 7 else 1
    while i < n:
        x = data[i]; best = None                    # (점수, 덮음, 함수)
        def cand(cov, cost, fn):
            nonlocal best
            sc = (cov / cost, cov)
            if best is None or sc > best[0]: best = (sc, cov, fn)
        # 1. 같은 바이트 런
        r = 1
        while i + r < n and data[i + r] == x and r < 257: r += 1
        if r >= 2:
            s = next((k for k in range(1, 8) if B[k] == x), 0)
            cost = (1 if s else 2) + (1 if r > 8 else 0)
            def f1(r=r, s=s, x=x):
                c = 7 if r > 8 else r - 2
                o.append((s << 3) | c)
                if not s: o.append(x); push(B, 'pb', x)
                if r > 8: o.append(r - 2)
                if c != 0: st['r12'] = x
            cand(r, cost, f1)
        # 2. x + R12 런
        q = 0
        while i + 1 + q < n and data[i + 1 + q] == st['r12'] and q < 256: q += 1
        if q >= 1:
            s = next((k for k in range(1, 8) if A[k] == x), 0)
            cost = (1 if s else 2) + (1 if q > 7 else 0)
            def f2(q=q, s=s, x=x):
                c = 7 if q > 7 else q - 1
                o.append(0xC0 | (s << 3) | c)
                if not s: o.append(x); push(A, 'pa', x)
                if q > 7: o.append(q - 1)
            cand(1 + q, cost, f2)
        # 3. 두 색 5화소
        if i + 5 <= n:
            seg = data[i:i + 5]; cs = sorted(set(seg))
            if len(cs) <= 2:
                c2 = st['c2']
                if c2 and all(v in c2 for v in seg):
                    def f3(seg=seg, c2=c2):
                        bits = 0
                        for v in seg: bits = bits << 1 | (1 if v == c2[1] and v != c2[0] else 0)
                        o.append(0x40 | 0x20 | bits)
                    cand(5, 1, f3)
                else:
                    a0 = seg[0]; a1 = next((v for v in seg if v != a0), a0)
                    def f3b(seg=seg, a0=a0, a1=a1):
                        bits = 0
                        for v in seg: bits = bits << 1 | (1 if v == a1 and v != a0 else 0)
                        o.append(0x40 | bits); o.extend((a0, a1)); st["c2"] = (a0, a1)
                    cand(5, 3, f3b)
        # 4. 8바이트 앞 복사
        if i >= 8:
            m = 0
            while i + m < n and data[i + m] == data[i + m - 8] and m < 8: m += 1
            if m >= 5:
                cand(m, 1, lambda m=m: o.append(0xA0 | (m - 5)))
        # 5. 기록 줄
        for H, bit in ((A, 0), (B, 8)):
            for j in range(1, 8):
                L = 0; jj = j
                while L < 4 and i + L < n and H[jj] == data[i + L]:
                    L += 1; jj = jj + 1 if jj < 7 else 1
                if L >= 1:
                    cand(L, 1, lambda L=L, j=j, bit=bit: o.append(0x80 | ((bit | j) << 2) | (L - 1)))
        # 6. 날 바이트
        L = 1
        while L < 4 and i + L < n: L += 1
        def f6(L=L):
            o.append(0x80 | (L - 1))
            for v in data[i:i + L]: o.append(v); push(A, 'pa', v)
        cand(L, L + 1, f6)
        (sc, cov, fn) = best
        fn(); i += cov
    o += b'\x0F\x00'
    return bytes(o)


def _moves(data, i, A, B, pa, pb, r12, c2):
    """(덮음, 내보낼 바이트, 새 상태) 들 — 상태 = (A, B, pa, pb, r12, c2)"""
    n = len(data); x = data[i]; out = []
    def nxt(p): return p + 1 if p < 7 else 1
    def pushA(v):
        A2 = list(A); A2[pa] = v; return tuple(A2), nxt(pa)
    def pushB(v):
        B2 = list(B); B2[pb] = v; return tuple(B2), nxt(pb)
    r = 1
    while i + r < n and data[i + r] == x and r < 257: r += 1
    for rr in sorted({r, min(r, 8), 2, 3} & set(range(2, r + 1))):
        c = 7 if rr > 8 else rr - 2
        s = next((k for k in range(1, 8) if B[k] == x), 0)
        nr = x if c != 0 else r12
        if s:
            b = bytes([(s << 3) | c]) + (bytes([rr - 2]) if rr > 8 else b'')
            out.append((rr, b, (A, B, pa, pb, nr, c2)))
        b = bytes([c, x]) + (bytes([rr - 2]) if rr > 8 else b'')
        B2, pb2 = pushB(x); out.append((rr, b, (A, B2, pa, pb2, nr, c2)))
    q = 0
    while i + 1 + q < n and data[i + 1 + q] == r12 and q < 256: q += 1
    for qq in sorted({q, min(q, 7)} & set(range(1, q + 1))):
        c = 7 if qq > 7 else qq - 1
        s = next((k for k in range(1, 8) if A[k] == x), 0)
        tail = bytes([qq - 1]) if qq > 7 else b''
        if s: out.append((1 + qq, bytes([0xC0 | (s << 3) | c]) + tail, (A, B, pa, pb, r12, c2)))
        A2, pa2 = pushA(x); out.append((1 + qq, bytes([0xC0 | c, x]) + tail, (A2, B, pa2, pb, r12, c2)))
    if i + 5 <= n:
        seg = data[i:i + 5]
        if len(set(seg)) <= 2:
            if c2 and all(v in c2 for v in seg):
                bits = 0
                for v in seg: bits = bits << 1 | (1 if v == c2[1] and v != c2[0] else 0)
                out.append((5, bytes([0x60 | bits]), (A, B, pa, pb, r12, c2)))
            a0 = seg[0]; a1 = next((v for v in seg if v != a0), a0); bits = 0
            for v in seg: bits = bits << 1 | (1 if v == a1 and v != a0 else 0)
            out.append((5, bytes([0x40 | bits, a0, a1]), (A, B, pa, pb, r12, (a0, a1))))
    if i >= 8:
        m = 0
        while i + m < n and data[i + m] == data[i + m - 8] and m < 8: m += 1
        if m >= 5: out.append((m, bytes([0xA0 | (m - 5)]), (A, B, pa, pb, r12, c2)))
    for H, bit in ((A, 0), (B, 8)):
        for j in range(1, 8):
            L = 0; jj = j
            while L < 4 and i + L < n and H[jj] == data[i + L]:
                L += 1; jj = nxt(jj)
            if L: out.append((L, bytes([0x80 | ((bit | j) << 2) | (L - 1)]), (A, B, pa, pb, r12, c2)))
    for L in range(1, min(4, n - i) + 1):
        A2 = list(A); p2 = pa
        for v in data[i:i + L]: A2[p2] = v; p2 = nxt(p2)
        out.append((L, bytes([0x80 | (L - 1)]) + bytes(data[i:i + L]), (tuple(A2), B, p2, pb, r12, c2)))
    return out


def enc_cells_beam(data, K=6):
    """자리마다 비용 낮은 상태 K 개를 남기는 빔 탐색(해제기 상태 그대로)"""
    n = len(data)
    z = tuple([0] * 8)
    beams = {0: {(z, z, 1, 1, 0, None): (0, None)}}       # 자리 → {상태: (비용, 되짚기)}
    import heapq
    pend = [0]; seen = {0}
    while pend:
        i = heapq.heappop(pend)
        if i >= n: continue
        cur = sorted(beams.pop(i).items(), key=lambda kv: kv[1][0])[:K]
        for stt, (cost, bp) in cur:
            node = (i, stt, cost, bp)
            for cov, b, ns in _moves(data, i, *stt):
                j = i + cov; nc = cost + len(b)
                d = beams.setdefault(j, {})
                if ns not in d or d[ns][0] > nc:
                    d[ns] = (nc, (node, b))
                if j not in seen: seen.add(j); heapq.heappush(pend, j)
    fin = min(beams[n].values(), key=lambda v: v[0])
    parts = []; bp = fin[1]
    while bp is not None:
        node, b = bp; parts.append(b); bp = node[3]
    return b''.join(reversed(parts)) + b'\x0F\x00'
