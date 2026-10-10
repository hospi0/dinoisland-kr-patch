# -*- coding: utf-8 -*-
r"""받아쓰기(work/asr/*.json) → 번역용 TSV (2026-10-10)
  열: id(음성_번호) · 시작(초) · 끝(초) · 원문(받아쓰기, 손 교정 전) · 번역(빈칸)
  순서 = 대본 DINA.CIT 에 음성이 처음 나오는 순서(대본에 없는 오프닝·엔딩 등은 뒤에 이름순)
  → work/text/voice.tsv(통짜) + work/text/split/voice_NNN.tsv(20 KB 단위, 사용자에게 주는 사본)
  python tools/extract.py
"""
import glob, json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
HEAD = 'id\t시작\t끝\t원문\t번역'
LIMIT = 20 * 1024                 # ★사용자 2026-10-10 «스플릿은 20kb 단위로»
# 위스퍼 환각(음악·효과음 구간에서 나옴) — 2026-10-10 보충 조각 218개 훑어 정함
HALLU = {'ご視聴ありがとうございました', 'チャンネル登録をお願いいたします', 'エンディング', '次回予告', '音楽', 'ゲーム',
         'キーボード', 'by H.', 'B', 'エス', 'ん', 'ありがとうございました。'}


def hallu(s):
    t = s['t'].strip().rstrip('。、.!！?？')                                 # ★끝 부호 떼고 비교(ご視聴…。 빠졌음 2026-10-10)
    if t in HALLU: return True
    if re.fullmatch(r'(.)\1{5,}[!！ー]*', t.replace('ー', '')): return True                  # うううう… 같은 한 글자 반복
    if re.fullmatch(r'((..?.?)\2{4,}).*', t) and len(set(t)) <= 4: return True            # だらんだらん… 반복
    if s.get('fill') and s['e'] - s['s'] > 6 and len(t) < 12: return True                 # 긴 구간에 짧은 글 = 노래·효과음
    return False


def order():
    b = open(os.path.join(ROOT, 'work', 'disc', 'DINA.CIT'), 'rb').read()
    seen = []
    for v in re.findall(rb':(S\w+),', b):
        v = v.decode()
        if v not in seen: seen.append(v)
    return seen


def rows():
    asr = {os.path.basename(p)[:-5]: json.load(open(p, encoding='utf-8')) for p in glob.glob(os.path.join(ROOT, 'work', 'asr', '*.json'))}
    seq = [v for v in order() if v in asr] + sorted(v for v in asr if v not in order())
    dp = os.path.join(ROOT, 'work', 'text', 'drop.txt')            # 사용자가 «없는 말»이라 한 조각
    drop = {l.split('	')[0].strip() for l in open(dp, encoding='utf-8')} if os.path.exists(dp) else set()
    out = []
    for v in seq:
        for k, s in enumerate(asr[v]['segs']):
            t = s['t'].replace('\t', ' ').strip()
            if t and not hallu(s) and '%s_%02d' % (v, k + 1) not in drop: out.append('%s_%02d\t%.2f\t%.2f\t%s\t' % (v, k + 1, s['s'], s['e'], t))
    return out


def write_split(stem, lines, d):
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, stem + '_*.tsv')): os.remove(f)
    parts = []; cur = [HEAD]
    for ln in lines:
        if len(('\n'.join(cur + [ln]) + '\n').encode('utf-8')) > LIMIT:
            parts.append(cur); cur = [HEAD]
        cur.append(ln)
    parts.append(cur)
    for i, p in enumerate(parts):
        open(os.path.join(d, '%s_%03d.tsv' % (stem, i + 1)), 'w', encoding='utf-8', newline='\n').write('\n'.join(p) + '\n')
    return len(parts)


def main():
    lines = rows()
    t = os.path.join(ROOT, 'work', 'text'); os.makedirs(t, exist_ok=True)
    open(os.path.join(t, 'voice.tsv'), 'w', encoding='utf-8', newline='\n').write('\n'.join([HEAD] + lines) + '\n')
    n = write_split('voice', lines, os.path.join(t, 'split'))
    print('줄 %d · 분할 %d개 → %s' % (len(lines), n, os.path.join(t, 'split')))


if __name__ == '__main__':
    main()
