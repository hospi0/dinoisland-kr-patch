# -*- coding: utf-8 -*-
r"""음성 ST2 전부 받아쓰기(2026-10-10) — 위스퍼 large-v3, 낱말 시각까지.
  ST2 = 머리 0x30 B + 16비트 BE PCM 모노 22,050 Hz → 16 kHz numpy 로 넘김.
  → work/asr/<이름>.json  {"name", "sec", "segs": [{"s","e","t","w": [[s,e,낱말]…]}]}  (이미 있으면 건너뜀)
  python C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr_all.py
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc

OUT = os.path.join(ROOT, 'work', 'asr')


def pcm(b):
    a = np.frombuffer(b[0x30:len(b) - (len(b) - 0x30) % 2], '>i2').astype(np.float32) / 32768
    idx = np.arange(0, len(a), 22050 / 16000)
    return np.interp(idx, np.arange(len(a)), a).astype(np.float32), len(a) / 22050


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(OUT, exist_ok=True)
    from faster_whisper import WhisperModel
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    names = sorted(n for n, _, _ in disc.files() if n.endswith('.ST2'))
    for k, n in enumerate(names):
        base = os.path.basename(n)[:-4]; p = os.path.join(OUT, base + '.json')
        if os.path.exists(p):
            continue
        a, sec = pcm(disc.read(n))
        seg, _ = m.transcribe(a, language='ja', beam_size=5, word_timestamps=True,
                              condition_on_previous_text=False, vad_filter=False)
        segs = [{'s': round(s.start, 2), 'e': round(s.end, 2), 't': s.text.strip(),
                 'w': [[round(w.start, 2), round(w.end, 2), w.word] for w in (s.words or [])]} for s in seg]
        json.dump({'name': base, 'path': n, 'sec': round(sec, 2), 'segs': segs}, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
        print('%3d/%d %s %.1f초 %d조각' % (k + 1, len(names), base, sec, len(segs)), flush=True)


if __name__ == '__main__':
    main()
