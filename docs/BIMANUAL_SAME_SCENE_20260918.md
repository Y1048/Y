# 기존 오른팔 씬에서 양팔 시뮬레이션

별도 BimanualSimulation 씬을 만들 필요가 없다. 기존 `SampleScene`에
왼손 binder와 모드 선택 컴포넌트를 추가하는 방식이다.

## 사용법

1. 기존 Unity 프로젝트의 **SampleScene**을 열고 Play를 끈다.
2. **G1 Teleop → Arms → Use Both Arms (Simulation)** 클릭 후 **Ctrl+S**.
   같은 메뉴를 반복해도 왼손 컴포넌트를 중복 생성하지 않는다.
3. `tools\START_BIMANUAL_UNITY_SIM.bat` 실행 후 Unity Play.
4. 기존 로봇 팔 표시에서 양손목을 각각 맞추고, 기존 hold-still 기준으로
   두 손 모두 준비되면 함께 engage한다. 한 손 pinch 0.5초는 양팔 복귀다.
5. READY 후 손을 맞춤 영역 밖으로 옮겼다가 다시 맞추면 재engage한다.

오른팔로 돌아갈 때: Play를 끄고 **G1 Teleop → Arms → Use Original Right Arm**,
Ctrl+S 후 기존 오른팔 BAT를 사용한다. 전환은 Play 중에 하지 않는다.
씬을 전환하거나 다른 프로젝트를 열 필요는 없다.

## 재사용/변경 범위

- 기존 오른손 binder 설정, 손목 소스, head heading, body translation 보정,
  상대이동 값, engage 정렬/안정 판정을 재사용한다.
- 왼손 binder는 현재 오른손 설정을 복제한 뒤 손/스켈레톤/목표 Transform과
  좌우 기준점을 바꾼다. 양팔 mode에서는 두 binder를 동시에 calibrate한다.
- 기존 `G1UnityRightArmPreview`, 공식 29축 모델, 머리 정렬/카메라/환경을 유지한다.
  양팔 mode에서는 별도 UDP feedback의 검증된 좌15..21/우22..28 값을 표시한다.
- 원래 오른팔 mode일 때는 preview의 기존 코드 경로와 원래 sender를 사용한다.
  양팔 mode에서는 원래 sender와 키패드 자동 송신을 막고 localhost5020만 사용한다.
- 양팔 mode 목표 마커는 **요청 목표**이며 충돌 검사된 미래의 도달 목표로
  표시하지 않는다. 기존 오른팔 mode의 feasible-target 표시는 변경하지 않는다.
- 기존 오른팔 IK는 보존됐다. 양팔 mode의 backend는 앞서 만든 coupled 14축
  후보를 사용한다. 기존 오른팔의 elbow assistance/torso target projection/
  orientation relaxation을 전부 동일하게 이식한 것은 아니다. 따라서 **씬과 입력
  흐름 통합 완료를 기존과 같은 자세/추종감 검증으로 해석하면 안 된다**.

## 검증

MuJoCo3.12.0 생성/프로토콜/loopback 테스트13개 통과.
실제 localhost feedback에서 양팔14축 배열/좌우순서/finite를 확인했다.
Unity/Meta/Newtonsoft/UI 실제 참조 DLL로 G1 runtime 소스와 새 editor 메뉴를
컴파일했다. Quest 손 추적 및 실제 Play/메뉴 적용은 사용자 시험이 남아 있다.

실제 G1, DDS, 물리 모터, PD 변경 없음. 별도 씬은 비교용으로 남는다.
기존 SampleScene은 메뉴 실행/저장 때 변경되며 새 왼손 컴포넌트와 모드 정보만
추가된다. 설치 전 로컬 코드/씬 백업을 `logs/backups/`에 보존한다.
