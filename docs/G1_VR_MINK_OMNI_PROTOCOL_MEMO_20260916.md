# Historical Memo — G1 VR / Mink / Omni Protocol (2026-09-16)

> **Historical reference only.** 이 문서는 2026-09-16 시점 설계 메모를 보존하기 위한 파일이다.
> 현재 실행 계약은 `docs/PROTOCOL.md`, `docs/ARCHITECTURE.md`, `docs/OMNI_WORLD_UPPER_BODY_20260922.md`를 따른다.

## 현재와 다른 핵심 사항

이 메모가 작성된 시점에는 오른손/오른팔 single-arm 경로와 UDP `5005/5006`이 중심이었다.

현재 기본 경로는 다음과 같다.

```text
Quest left/right hands
 -> Unity G1BimanualSimulationSender
 -> UDP 127.0.0.1:5020
 -> g1_bimanual_runtime.py
 -> 14-DoF bimanual Mink/MuJoCo
```

현재 schema/frame:

```text
g1.bimanual.unity.sim.v4
unity_display_world_v1
```

현재 speed profile:

```text
proximal 90 deg/s
wrist 180 deg/s
acceleration 90 deg/s²
IK tracking rate 1.0 /s
```

현재 PiP는 G1 `RobotRoot`에 parent된다.

## 이 파일을 남기는 이유

- 초기 Omni/VR/Mink 설계 의도 확인
- 과거 5005/5006 packet과 commit 비교
- regression 시 historical context 확인

새 개발자는 이 파일을 current source of truth로 사용하면 안 된다.

현재 문서 읽는 순서:

1. `README.md`
2. `docs/CHAT_HANDOFF.md`
3. `docs/ARCHITECTURE.md`
4. `docs/PROTOCOL.md`
5. `docs/OMNI_WORLD_UPPER_BODY_20260922.md`
