# -*- coding: utf-8 -*-
r"""다이노 아일랜드 자막 PoC (2026-10-10) — 첫 대사 S00100 두 쪽을 NBG3 에 띄운다.
  싣기:  BLDANIM.BIN 끝(0x0602F850 = BSS 시작)에 «복사 토막 + 상주 몸»을 붙인다.
         진입 리터럴 0x06010010(→ main 0x060119AC)을 복사 토막으로 → BSS 를 지우기 전에 몸을 RES(0x06049000, BSS 밖)로 옮기고 main 으로.
         ★0LOAD 는 0x06020000‥0x0605FFFF 를 지운 뒤 BLDANIM 을 디렉터리 크기대로 읽는다(크기 상수 없음).
  디스크: 늘어난 BLDANIM 을 트랙 1 뒷간격(마지막 파일 뒤 150섹터, 0 데이터) 첫머리 LBA 260771 로 옮김 → 트랙 크기·DIN_TRY(트랙 2 가리킴) 그대로.
  훅:   VBI 등록 리터럴 0x06018178(→ 0x06017F48)을 감싸개로 — 원래 VBI 뒤에 자막 처리.
         음성 이름 0x06030AB0 = 'S00100' 이고 시각 0x06046E74(1/60초, 음성 재생 위치) 가 쪽 구간 안이면 그 쪽.
  표시:  NBG3 16색 1×1 셀, 1워드 PN(PNCN3 0x80EE: 보충 팔레트 7·보충 문자 0xE), 지도 VRAM 0x74000(MPAB3 0x3A), 셀 0x76000(번호 0x300 = 빈칸, 0x301‥)
         팔레트 127(CRAM 0xFE0): 1 = 검정 테두리, 15 = 흰 글자. B1 접근 주기 1244/0FEE → 1244/037E(★원래 칸은 그대로, 빈 칸 T5 = N3 PN · T6 = N3 CG — 예전 1344/072E 는 N2 PN 을 T6 으로 옮겨 오프닝·대사 NBG2 가 깨짐, 사용자 2026-10-10)
         켤 때 BGON 000F·CHCTLB 0002·PRINB 0705, 끌 때 대사 모드 값 0007·0022·0005·1244/0FEE 로 되돌림.
  python tools/poc.py   → work/out/Dino Island (Japan) (Track 1).bin  (먼저 sh2sim 검산)
"""
import os, shutil, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.append(r'C:\claude\project\burningrangers-kr-patch\tools')   # 맨 뒤 — 같은 이름 disc.py 가 우리 것을 가리지 않게
import glyphpack as G
from sh2asm import A
import sh2sim as S
import disc

EXE = os.path.join(ROOT, 'work', 'disc', 'BLDANIM.BIN')
OUT = os.path.join(ROOT, 'work', 'out', 'Dino Island (Japan) (Track 1).bin')
LOAD = 0x06010000; BSS = 0x0602F850; RES = 0x06049000
MAIN = 0x060119AC; ENTRY_LIT = 0x06010010
VBI = 0x06017F48; VBI_LIT = 0x06018178
VNAME = 0x06030AB0; CLOCK = 0x06046E74          # ★E74 = 음성 재생 시각(컷이 먼저 넘어가도 계속 감) · E80 = 보이는 컷 시각(컷 경계로 뜀) — 2026-10-10 실기
VDP2 = 0x25F80000; MAPV = 0x25E74000; CELLV = 0x25E76020; PALV = 0x25F00000 + 127 * 32
BLANK = 0xF300; FIRST = 0xF301
NEW_LBA = 260771

REGS_ON = [(0x20, 0x000F), (0x1C, 0x1244), (0x1E, 0x037E), (0x2A, 0x0002), (0x36, 0x80EE),
           (0x4C, 0x3A3A), (0x4E, 0x3A3A), (0x94, 0), (0x96, 0), (0xFA, 0x0705)]
REGS_OFF = [(0x20, 0x0007), (0x1C, 0x1244), (0x1E, 0x0FEE), (0x2A, 0x0022), (0xFA, 0x0005)]

# 첫 대사(받아쓰기 S00100 0.56‥8.28초 / 9.32‥12.94초) — 시각은 1/60초
PAGES = [(30, 556, ['초코,초코 샀고,감자칩도 샀고,', '젤리랑 소프트아이스크림,쿠키도 샀어.']),
         (556, 800, ['아,아세롤라 주스 깜빡했다.'])]


def page_blob(lines):
    w8, nrow, chars = G.layout(lines)
    px = G.reference(w8, nrow, chars)
    cells = G.cells_4bpp(px, w8, nrow)
    n = w8 * nrow; assert n <= 255, n
    row0 = 27 - nrow; col0 = (40 - w8) // 2; assert col0 >= 0, w8
    return struct.pack('>4H', w8, nrow, (row0 * 64 + col0) * 2, n) + cells


DATA = RES + 0x400                                   # 자료 자리(코드는 그 앞 1 KB 안)


def data_part():
    data = bytearray(); lab = {}
    def put(name, b):
        nonlocal data
        data += bytes(-len(data) % 4); lab[name] = DATA + len(data); data += b
    put('cur', bytes(4))
    put('ron', b''.join(struct.pack('>HH', *x) for x in REGS_ON) + b'\xff\xff')
    put('roff', b''.join(struct.pack('>HH', *x) for x in REGS_OFF) + b'\xff\xff')
    pal = [0] * 16; pal[1] = 0x8000; pal[15] = 0xFFFF
    put('pal', struct.pack('>16H', *pal))
    for i, (_, _, l) in enumerate(PAGES): put('p%d' % i, page_blob(l))
    put('tab', b''.join(struct.pack('>iiI', t0, t1, lab['p%d' % i]) for i, (t0, t1, _) in enumerate(PAGES)) + struct.pack('>i', -1))
    return bytes(data), lab


def assemble():
    data, dlab = data_part()
    a = A(RES); a.lab.update(dlab); W = a.w
    # ---- 감싸개(VBI) ----
    a.L('vbi'); W(0x4F22); a.ld(0, VBI); W(0x400B, 0x0009)
    a.br('bsr', 'sub'); W(0x0009)
    W(0x4F26, 0x000B, 0x0009)
    # ---- sub ----
    a.L('sub'); W(0x4F22)
    a.ld(1, VNAME); W(0x6012); a.ld(2, 0x53303031); W(0x3020); a.br('bf', 'none')   # 'S001'
    W(0x8512, 0x600D); a.ld(2, 0x3030); W(0x3020); a.br('bf', 'none')              # '00'
    a.ld(1, CLOCK); W(0x6312)                                                       # r3 = 시각
    a.ld(4, 'tab')
    a.L('lp'); W(0x6042, 0x4011); a.br('bf', 'none')                                # 끝(-1)
    W(0x3303); a.br('bf', 'nx')                                                     # 시각 >= t0
    W(0x5041, 0x3037); a.br('bf', 'nx')                                             # t1 > 시각
    W(0x5542); a.br('bra', 'have'); W(0x0009)
    a.L('nx'); W(0x740C); a.br('bra', 'lp'); W(0x0009)
    a.L('none'); W(0xE500)
    a.L('have'); a.ld(1, 'cur'); W(0x6012, 0x3050); a.br('bt', 'same')
    W(0x2152, 0x2558); a.br('bt', 'off')
    a.br('bsr', 'draw'); W(0x0009)
    a.br('bra', 'on'); W(0x0009)
    a.L('same'); W(0x2558); a.br('bt', 'ret')
    a.L('on'); a.ld(1, 'ron'); a.br('bsr', 'wregs'); W(0x0009)
    a.ld(1, 'pal'); a.ld(2, PALV); W(0xE308)
    a.L('pl'); W(0x6016, 0x2202, 0x7204, 0x4310); a.br('bf', 'pl')
    a.br('bra', 'ret'); W(0x0009)
    a.L('off'); a.ld(1, 'roff'); a.br('bsr', 'wregs'); W(0x0009)
    a.L('ret'); W(0x4F26, 0x000B, 0x0009)
    # ---- wregs(r1 = (u16 자리, u16 값)…, 0xFFFF 끝) ----
    a.L('wregs'); a.ld(2, VDP2)
    a.L('wl'); W(0x6015, 0x4011); a.br('bf', 'wd')
    W(0x6303, 0x332C, 0x6015, 0x2301); a.br('bra', 'wl'); W(0x0009)
    a.L('wd'); W(0x000B, 0x0009)
    # ---- draw(r5 = 쪽) ----
    a.L('draw')
    a.ld(1, MAPV); a.ld(2, BLANK << 16 | BLANK); a.ld(3, 28 * 64 * 2 // 4)
    a.L('mf'); W(0x2122, 0x7104, 0x4310); a.br('bf', 'mf')                          # 지도 0‥27행 빈칸
    W(0x6153, 0x7108, 0x8553, 0x600D, 0x6303, 0x4308, 0x4300)                       # r1 = 셀, r3 = 셀 수×8 롱
    a.ld(2, CELLV)
    a.L('cc'); W(0x6016, 0x2202, 0x7204, 0x4310); a.br('bf', 'cc')
    W(0x8551, 0x600D, 0x6603, 0x8552, 0x600D); a.ld(2, MAPV); W(0x320C)             # r6 = nrow · r2 = 지도 자리
    a.ld(7, FIRST)
    a.L('rw'); W(0x6051, 0x600D, 0x6403, 0x6123)
    a.L('cl'); W(0x2171, 0x7102, 0x7701, 0x4410); a.br('bf', 'cl')
    W(0xE040, 0x4000, 0x320C, 0x4610); a.br('bf', 'rw')
    W(0x000B, 0x0009)
    code = a.build(); assert len(code) <= DATA - RES, len(code)
    return code + bytes(DATA - RES - len(code)) + data, a.lab


def stub(nlong):
    a = A(BSS); W = a.w
    a.ld(1, BSS + 0x40); a.ld(2, RES); a.ld(3, nlong)
    a.L('lp'); W(0x6016, 0x2202, 0x7204, 0x4310); a.br('bf', 'lp')
    a.ld(0, MAIN); W(0x402B, 0x0009)
    c = a.build(); assert len(c) <= 0x40, len(c)
    return c + bytes(0x40 - len(c))


def build_exe():
    exe = bytearray(open(EXE, 'rb').read()); assert len(exe) == BSS - LOAD
    res, lab = assemble()
    res += bytes(-len(res) % 4)
    st = stub(len(res) // 4)
    assert struct.unpack_from('>I', exe, ENTRY_LIT - LOAD)[0] == MAIN
    assert struct.unpack_from('>I', exe, VBI_LIT - LOAD)[0] == VBI
    struct.pack_into('>I', exe, ENTRY_LIT - LOAD, BSS)
    struct.pack_into('>I', exe, VBI_LIT - LOAD, lab['vbi'])
    return bytes(exe) + st + res, res, lab


# ============ 검산(sh2sim) ============
def check(new, res, lab):
    ok = True
    m = S.Mem(); m.add(0x06000000, 0x100000); m.add(0x05E00000, 0x80000); m.add(0x05F00000, 0x1000); m.add(0x05F80000, 0x200)
    m._f(LOAD)[0][0x10000:0x10000 + len(new)] = new
    S.run(m, BSS, stop=MAIN)
    got = bytes(m.r8(RES + i) for i in range(len(res)))
    print('① 복사 토막: 몸 %d B → 0x%08X %s' % (len(res), RES, got == res)); ok &= got == res
    for nm, v in (('S00100.ST2', 100), ('S00100.ST2', 300), ('S00100.ST2', 700), ('S00100.ST2', 900), ('S00200.ST2', 300)):
        for i, ch in enumerate(nm.encode() + b'\0'): m.w8(VNAME + i, ch)
        m.w32(CLOCK, v)
        S.run(m, lab['vbi'], calls={VBI: lambda r, mm: None})
        bgon = m.r16(VDP2 + 0x20); want = None
        for k, (t0, t1, l) in enumerate(PAGES):
            if nm == 'S00100.ST2' and t0 <= v < t1: want = k
        if want is None:
            good = bgon == 0x0007 or bgon == 0
            print('  %s %4d → 없음 BGON %04X %s' % (nm, v, bgon, good)); ok &= good; continue
        w8, nrow, chars = G.layout(PAGES[want][2]); px = G.reference(w8, nrow, chars); cells = G.cells_4bpp(px, w8, nrow)
        gc = bytes(m.r8(CELLV + i) for i in range(len(cells)))
        row0 = 27 - nrow; col0 = (40 - w8) // 2
        mp = [m.r16(MAPV + 2 * (r * 64 + c)) for r in range(28) for c in range(64)]
        exp = [BLANK] * (28 * 64)
        for y in range(nrow):
            for x in range(w8): exp[(row0 + y) * 64 + col0 + x] = FIRST + y * w8 + x
        regs = all(m.r16(VDP2 + o) == val for o, val in REGS_ON)
        pal = m.r16(PALV + 2) == 0x8000 and m.r16(PALV + 30) == 0xFFFF
        good = gc == cells and mp == exp and regs and pal
        print('  %s %4d → 쪽 %d 셀 %s 지도 %s 레지스터 %s 팔레트 %s' % (nm, v, want, gc == cells, mp == exp, regs, pal)); ok &= good
    return ok


def write_disc(new):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    import importlib.util                                       # 유나 리믹스 iso.py(섹터 헤더·EDC/ECC) — 버닝 레인저에도 같은 이름이 있어 경로로 직접
    sp = importlib.util.spec_from_file_location('yuna_iso', r'C:\claude\project\yunaremix-kr-patch\tools\iso.py')
    iso = importlib.util.module_from_spec(sp); sp.loader.exec_module(iso)
    shutil.copyfile(disc.BIN, OUT)
    n = (len(new) + 2047) // 2048
    with open(OUT, 'r+b') as f:
        assert NEW_LBA + n <= os.path.getsize(OUT) // 2352
        for i in range(n):                                     # 뒷간격이 정말 0 인지
            f.seek((NEW_LBA + i) * 2352 + 16); assert f.read(2048) == bytes(2048), NEW_LBA + i
        for i in range(n):
            f.seek((NEW_LBA + i) * 2352); f.write(iso.sector(NEW_LBA + i, new[i * 2048:(i + 1) * 2048].ljust(2048, b'\0')))
        pvd = disc.sec(f, 16); rl, rs = struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0]
        for k in range((rs + 2047) // 2048):
            d = bytearray(disc.sec(f, rl + k)); i = 0; hit = False
            while i < 2048 and d[i]:
                L = d[i]
                if d[i + 33:i + 33 + d[i + 32]] == b'BLDANIM.BIN;1':
                    struct.pack_into('<I', d, i + 2, NEW_LBA); struct.pack_into('>I', d, i + 6, NEW_LBA)
                    struct.pack_into('<I', d, i + 10, len(new)); struct.pack_into('>I', d, i + 14, len(new)); hit = True
                i += L
            if hit:
                f.seek((rl + k) * 2352); f.write(iso.sector(rl + k, bytes(d))); break
        else:
            raise SystemExit('BLDANIM 기록 없음')
    fs = {nm: (l, s) for nm, l, s in disc.files(OUT)}
    assert fs['/BLDANIM.BIN'] == (NEW_LBA, len(new)) and disc.read('/BLDANIM.BIN', OUT) == new
    print('디스크: BLDANIM %d B → LBA %d (%d섹터) · %s' % (len(new), NEW_LBA, n, OUT))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    new, res, lab = build_exe()
    print('BLDANIM %d → %d B (토막 64 + 몸 %d B, 감싸개 0x%08X)' % (BSS - LOAD, len(new), len(res), lab['vbi']))
    if not check(new, res, lab):
        raise SystemExit('검산 실패')
    if '--write' in sys.argv:
        write_disc(new)


if __name__ == '__main__':
    main()
