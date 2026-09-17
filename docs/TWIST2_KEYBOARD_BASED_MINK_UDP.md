# 기존 키보드 C++ 기반 Mink UDP 실험

## 원본 보존과 새 실행파일

원본 `/home/unitree/g1_right_arm_trial` 소스/실행파일을 수정하지 않았다. 기존 명령으로
언제든 실행할 수 있다. 새 버전은 `/home/unitree/g1_mink_udp_trial_20260908`에 별도 설치한다.
둘을 동시에 실행하지 않는다. 이번 사용자 요청은 기존 PC배치 대신 G1별도버전 전송·컴파일을 허용했다.

새 소스: experiments/twist2_right_arm_manual/twist2_mink_udp_trial.cpp.
기존 twist2_right_arm_trial.cpp의 복사본에 UDP입력/초기팔자세/입력watchdog를 연결했다.
기존 snapshot의 age혼용은 같은 LowState/receipt를 검증하도록 고쳤고 중복tick은 신선도를 갱신하지 않는다.

## 달라진 동작

- P 시작확인/R1 유지/Select·B 중단/실행중 p 중단은 유지.
- 기존 하체정책과 단일전신 rt/lowcmd 소유구조 유지. AI/Regular위에 오른팔만 추가하는 구조 아님.
- capture1초/하체blend4초 후 두팔을 MuJoCo 준비자세로 .08rad/s 이동한다.
- 왼팔 [10,22,0,55,0,0,0]도, 오른팔 [10,-22,0,55,0,0,0]도.
  배열순서는 shoulder pitch/roll/yaw,elbow,wrist roll/pitch/yaw.
- `udp_ready` 표시 후 Mink 첫 active부터 오른팔 절대각도를 입력한다.
  목표-입력 .025rad 정렬조건, 전신 desired-q 준비조건 및 ±10도상대이동창은 이 버전에 없다.
  큰목표차이도 .08rad/s로 점진추종하며 목표초과 없이도달. 준비전engage는 거부한다.
- 실측-명령 .25rad 추종보호는 유지했고 초기이동하는상체12..28에적용한다.
  입력오차와실측이상을구분한다. 실측속도1.5rad/s,상태/CRC/온도/fault/관절/torque/timeout 보호도 유지.
- 속도는 키보드 기본1배=.08rad/s 고정. 이 버전에서1..9키로속도를변경하지 않는다.
  Mink QP와trajectory의 속도도환경변수 G1_TWIST2_KEYBOARD_RATE=1일때 .08로일치.
  기존실행기본 .16 및 기존가속도 .32rad/s²/jerk 설정은 그대로다.
- 입력중단/오류는latch, 해제후자동재개안함. 입력간격250ms timeout과기존정책watchdog유지.
  오류/pinch의damping은Ctrl+C전까지지속할수있고AI자동복귀없음.

## 실행 전

기존 MuJoCo 창을 정상 종료한다. 준비중확인한PID41228은simulation_312.py였고 종료하지 않았다.
5005는Mink가받고5008은relay가받는다. 동시에shadow/Gate7 dry-run을실행하지 않는다.
새Mink는검증된live entry의Mink결과만출력한다. simulation-only파일을live로재표시하지 않는다.
Unity 표시는 simulation 유지, Unity에서 SampleScene Play/hand tracking 준비.
손은 `udp_ready` 전까지engage영역밖에둔다. 별도담당자가R1과Select/B를담당한다.
지지/양발하중/안정적인AI상태를확인한다. 시작부터손이몸에끼어있다면실행으로밀어내려하지않는다.

## 사용자 직접 실행: 배치파일 하나

기존 Mink/Input 및 relay 창을 먼저 정상 종료한 뒤 프로젝트 폴더에서 실행한다.

```powershell
.\tools\START_TWIST2_MINK_UDP.bat
```

더블클릭도 같다. Input·Relay·Robot 창 세 개를 열고 같은 세션 토큰을 자동 전달한다.
각 PowerShell 창은 `-ExecutionPolicy Bypass`로 시작하므로 이 실행 경로에서는
별도 실행정책 설정이나 토큰 복사가 필요 없다. 시스템 전체 정책은 변경하지 않는다.
Robot 창에서 SSH 비밀번호를 입력하고 기존 P 시작확인/R1 유지 절차를 수행한다.
세 창을 열었다는 메시지는 각 프로그램의 준비 완료를 뜻하지 않으므로 오류를 확인한다.
5005/5008이 이미 점유돼 있으면 새 창을 열지 않고 PID를 표시한다. 프로세스는 자동 종료하지 않는다.
Unity Play는 별도로 준비한다. 자동 키 입력이나 자동 재시도는 없다.
Relay의 `[WAIT] No Unity input session yet`는 첫 Unity 유효 입력 전 대기이며
해당 패킷은 G1으로 전달하지 않는다. Unity Play와 손 추적을 확인한다.
`[RELAY] First token-bound live Mink packet forwarded`가 실제 첫 전달 표시다.
이 표시는 G1 수신/팔 추종 성공을 뜻하지 않는다. `udp_ready` 전에는 engage하지 않는다.

개별 실행은 배치파일에 `-Mode Input`, `-Mode Relay -RelayToken 토큰`,
`-Mode Robot -RelayToken 토큰`을 전달한다. Relay와 Robot에는 동일한 영숫자 16~128자 토큰을 쓴다.
`-Mode All -Preview`는 실행 계획만 출력하며 창/SSH/모터 명령을 실행하지 않는다.

G1에서P확인후R1유지, 초기자세이동과udp_ready 확인후engage→작은손이동→pinch해제.
정책구간300초에는초기팔이동시간이포함된다. 끝나면damping이며AI복귀는수동이다.
바로다시실행하지말고결과/현재상태를확인한다.

## 검증 범위와 남은 항목

SDK없는표적시험: 초기속도/초기완료/입력차이허용/오른팔만갱신/초과없음/해제·오류·latch/timeout 통과.
원래키보드원본 SHA E61D8A3C...CC09F, G1원본ELF a3c1e936...4f60 보존.
MuJoCo 준비자세의기존오른팔충돌검사 최소거리약40.38mm.
저장LowState에서시작한경로의기존오른팔검사 최소28.11mm.
별도확장한양손-다리거리조회는중간에0을반환했다. 따라서전경로무접촉검증은완료되지않았다.
실제시작자세/하체정책움직임/접촉하중과3.11거리계산의차이는아직확인필요하다.
준비자세코드추가는초기충돌해결의실기검증을뜻하지않는다. 현재물리실행/VR화면검증안함.

## 추후 속도·가속도 검토

이번에는 기존키보드기본속도에맞췄다. EDU모터최대수치만으로VR속도를정하지않고,
관절별사양/부하·토크/감속비/지연/충돌여유와실측추종을함께검토하는작업으로남긴다.
기존9배속선택가능은그속도로새VR경로가검증됐다는뜻이아니다.
새G1실험폴더는추후삭제대상이며원본폴더와구분한다.
