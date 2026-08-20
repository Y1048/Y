# Legacy Unity UDP Bridge Notes

이 폴더는 초기 Unity-UDP 연동 실험 코드 보관용이다. 현재 실행 중인 Unity 구현은
프로젝트 루트의 `Unity_G1_Quest3S`에 있으며, 전체 테스트는
`START_VR_HAND_TO_MUJOCO.bat`으로 실행한다.

## UDP 계약

- 수신 주소: `127.0.0.1:5005`
- 현재 수신기: `../scripts/g1_right_arm_udp_ik_demo.py`
- 최소 입력 예시:

```json
{
  "right": {
    "pos": [0.42, -0.16, 1.05]
  }
}
```

현재 Unity 송신기는 위치뿐 아니라 손목 회전, tracking 유효성 및 timestamp를 함께 보낸다.

## 보관된 코드

- `EditorTestUdpHandSender.cs`: Unity Editor에서 가짜 위치를 보내던 초기 실험
- `XRHandsUdpSender.cs`: XR Hands 기반 초기 송신 실험
- `g1_quest3s_scripts`: 현재 Oculus/Meta 기반 프로젝트 이전에 만든 XR 및 HUD 실험 코드

이 파일들은 참고용이며 `Unity_G1_Quest3S/Assets`에 자동 복사해서 사용하지 않는다.
