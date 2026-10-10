# -*- coding: utf-8 -*-
r"""받아쓰기 구멍 메우기(2026-10-10) — 1차(asr_all)에서 위스퍼가 30초 창을 통째로 건너뛴 곳이 많았다(소리 있는 초의 77%만 덮음).
  음성마다 «소리 있음(1초 RMS > 1500) & 조각 없음» 구간을 찾아(앞뒤 1초 여유, 2초 이상) 그 부분만 잘라 다시 받아쓰고 조각에 끼운다.
  잘라 넣은 조각은 "fill": 1 표시. 두 번 돌려도 같은 곳을 또 넣지 않게 덮인 곳은 건너뜀.
  python C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_fill.py
"""
import glob, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc
from asr_all import pcm, OUT


def gaps(d, x22):
    r = np.array([np.sqrt(np.mean(x22[i:i + 22050] ** 2)) for i in range(0, len(x22) - 22050 + 1, 22050)]) * 32768
    cov = np.zeros(len(r) + 2, bool)
    for s in d['segs']:
        cov[int(s['s']):int(s['e']) + 1] = True
    miss = (r > 1500) & ~cov[:len(r)]
    out = []; i = 0
    while i < len(miss):
        if miss[i]:
            j = i
            while j < len(miss) and (miss[j] or (j + 1 < len(miss) and miss[j + 1])): j += 1
            if j - i >= 2: out.append((max(0, i - 1), min(len(r), j + 1)))
            i = j
        i += 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    from faster_whisper import WhisperModel
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    tot = 0
    for p in sorted(glob.glob(os.path.join(OUT, '*.json'))):
        d = json.load(open(p, encoding='utf-8'))
        b = disc.read(d['path'])
        x22 = np.frombuffer(b[0x30:len(b) - (len(b) - 0x30) % 2], '>i2').astype(np.float32) / 32768
        a16, _ = pcm(b)
        add = []
        for g0, g1 in gaps(d, x22):
            piece = a16[int(g0 * 16000):int(g1 * 16000)]
            seg, _ = m.transcribe(piece, language='ja', beam_size=5, word_timestamps=True, condition_on_previous_text=False)
            for s in seg:
                t = s.text.strip()
                if not t: continue
                add.append({'s': round(g0 + s.start, 2), 'e': round(g0 + s.end, 2), 't': t, 'fill': 1,
                            'w': [[round(g0 + w.start, 2), round(g0 + w.end, 2), w.word] for w in (s.words or [])]})
        if add:
            d['segs'] = sorted(d['segs'] + add, key=lambda s: s['s'])
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
            tot += len(add)
            print('%s +%d조각' % (d['name'], len(add)), flush=True)
    print('합계 +%d조각' % tot)


if __name__ == '__main__':
    main()
