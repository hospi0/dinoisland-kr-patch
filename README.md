# 다이나♥아이랑 한글 패치 (だいな♥あいらん / Dino Island, 세가 새턴 일본판)

- 대상: Dino Island (Japan) — 트랙 1에 xdelta 패치 (트랙 2 오디오·cue 는 그대로)
- 내려받기: 릴리즈의 `DinoIsland_KR_v0.8.zip` — 안의 readme.txt 에 원본·패치 md5 와 적용 방법

| 트랙 | 원본 md5 | 패치 md5 |
|---|---|---|
| Track 1 | `80C2E8DE32C19842C163930B5FC01496` | `4C1FC86A5469F4466901A70A3F4B3516` |

## 바뀌는 것 (v0.8)
- 음성 자막 1,871줄(음성 238개) — 원래 글자 대사가 없는 게임이라 새로 넣음(음성 재생 위치에 맞춰 넘어가고, 일시정지·뒤로가기도 따라감)
- 선택지 76개
- 첫 로고 판권, 경고 화면 2장, 타이틀(로고·메뉴·판권), 저장 화면

## 알려진 점
- 자막 원문은 음성을 받아쓴 것이라 일부 대사가 실제와 다를 수 있음
- 리플레이 화면 무늬, 오프닝 지명 등 일부 그림 글자는 아직 일본어

## 저장소
- `tools/build.py` 빌더 · `hook.py` 자막 훅(SH-2, VDP1 스프라이트) · `poc2.py` 음성 머리에 자막 싣기 · `case.py` 선택지 · `gfx.py`/`gicodec.py`/`savefont.py` 그림 · `iso.py` 디스크 재배치 · `make_dist.py` 배포
- `tools/test_vdp1.py` SH-2 흉내기(`sh2sim.py`) 검산
- `work/text/voice.tsv` 음성 자막(id·시각·받아쓰기·번역) · `fixes.tsv` 교정 · `choice.tsv`/`choice_ko.py` 선택지
- `docs/` 조사·작업 기록
