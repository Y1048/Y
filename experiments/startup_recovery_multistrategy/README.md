# Experimental multi-strategy Startup Recovery

현재 Startup Recovery와 활성 실행 파일을 변경하지 않고 여러 초기 접촉 탈출
방향을 비교하는 오프라인 실험이다.

```powershell
.\experiments\startup_recovery_multistrategy\TEST_MULTI_STRATEGY.bat
```

실험기는 현재 캡처된 오른팔 7관절 자세에 대해 다섯 개의 탈출 벡터를 각각 별도
프로세스에서 실행한다. 모든 기존 관절·충돌·속도·가속도·jerk·Safety Gate 검사를
통과한 후보만 비교한다. 초기 접촉 해소 이후 최소 충돌 여유가 가장 큰 후보에서
`0.5 mm` 이내인 경로를 같은 안전 등급으로 취급하고, 그중 완료 시간이 짧은
후보를 선택한다. 이는 서브밀리미터 수치 잡음 때문에 불필요하게 긴 경로를 고르는
것을 막기 위한 실험 기준이다.

결과는 다음 위치에만 저장된다.

```text
logs/experiments/startup_recovery_multistrategy/
```

선택된 경로를 MuJoCo에서 보려면 다음을 실행한다.

```powershell
.\experiments\startup_recovery_multistrategy\VIEW_SELECTED.bat
```

이 실험은 Unitree SDK, DDS, UDP, G1 연결, command publisher를 사용하지 않는다.
결과의 `hardware_ready`와 `command_output_enabled`는 항상 `false`다.
