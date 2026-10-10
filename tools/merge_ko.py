# -*- coding: utf-8 -*-
r"""사용자 번역(my files/번역/voice_*.tsv) → work/text/voice.tsv «번역» 열 (2026-10-10)
  id 로 맞춤 — 원문 TSV 에 없는 id, 번역 파일에 없는 id 를 보고. my files 는 읽기만.
  python tools/merge_ko.py
"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rules
SRC = os.path.join(ROOT, 'my files', '번역')
TSV = os.path.join(ROOT, 'work', 'text', 'voice.tsv')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ko = {}; dup = []
    for p in sorted(glob.glob(os.path.join(SRC, 'voice_*.tsv'))):
        for ln in open(p, encoding='utf-8-sig').read().splitlines()[1:]:
            c = ln.split('\t')
            if not c[0].strip(): continue
            if c[0] in ko: dup.append(c[0])
            ko[c[0]] = rules.apply(c[4].strip()) if len(c) > 4 else ''     # 용어 규칙(rules.TERMS)
    fp = os.path.join(ROOT, 'work', 'text', 'fixes.tsv')            # 고침 목록(사용자 승인) — 번역 파일을 다시 받아도 유지
    if os.path.exists(fp):
        for ln in open(fp, encoding='utf-8').read().splitlines()[1:]:
            c = ln.split('	')
            if c[0] in ko: ko[c[0]] = rules.apply(c[1].strip())
            else: print('고침 목록 id 없음', c[0])
    rows = open(TSV, encoding='utf-8').read().splitlines()
    out = [rows[0]]; ids = set(); miss = []
    for r in rows[1:]:
        c = r.split('\t'); ids.add(c[0])
        if c[0] not in ko: miss.append(c[0])
        c = c[:4] + [ko.get(c[0], '')]
        out.append('\t'.join(c))
    extra = sorted(set(ko) - ids)
    open(TSV, 'w', encoding='utf-8', newline='\n').write('\n'.join(out) + '\n')
    empty = [r.split('\t')[0] for r in out[1:] if not r.split('\t')[4]]
    print('번역 %d줄 · 원문 %d줄 · 원문에 없는 id %d %s · 번역 없는 id %d %s · 중복 %s · 빈 번역 %d'
          % (len(ko), len(rows) - 1, len(extra), extra[:5], len(miss), miss[:5], dup[:5], len(empty)))


if __name__ == '__main__':
    main()
