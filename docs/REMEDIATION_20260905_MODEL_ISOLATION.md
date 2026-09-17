# 모델 생성 격리

## 2026-09-06 송신 모델 정보 기록

### 검토

캡처 프로그램이 별도로 계산한 모델 해시는 송신기 모델과 다를 수 있다.
송신기가 실제 로드한 XML 정보를 패킷에 넣어야 한다.

### 코드 수정

virtual-center 진입점의 공통 loader metadata를 packet.model_metadata에 추가했다.
기존 recorder의 exact payload 저장으로 metadata도 보존된다. decoder는 올바른
SHA256 형식과 동일 session 내 metadata 불변성을 확인한다. 과거 캡처는 허용한다.

### 테스트

logs/test_results/r53_capture_identity_20260906.xml.
소켓/뷰어 대역 main과 합성 캡처로 정상/과거/불일치/잘못된 해시를 검사한다.

### 남은 항목

현재 재생 모델 자동 대조 및 외부 자산 binding은 미구현. prototype 직접 송신도 남음.
이 정보는 XML만 식별하며 실제 기기의 진위나 물리 안전을 증명하지 않는다.

## 2026-09-06 Jog 허가 모델 연결

### 검토

실제 validator의 모델과 허가의 공유 XML 해시가 달랐다. 기존 R53/R42 후속이다.

### 코드 수정

validator가 LoadMinkModelWithMetadata로 로드하고 허가 payload에 metadata를 전달한다.
지원 entry는 해당 metadata로 provenance를 생성하고 실행 검사기의 metadata와 비교한다.
model_binding 추가로 기존 허가는 거부된다. 누락 metadata도 거부한다.
모델 controller/common 소스 해시를 포함하고 write_json wrapper를 finally에서 복원한다.
제어 설정/속도/게인/충돌 수치는 변경하지 않았다.

### 테스트

r53_jog_model_20260906.xml: 57 passed.
r53_jog_entry_20260906.xml: 18 passed.
모델 불일치/구형 허가/metadata 누락 거부와 공유 XML 부재를 확인했다.
Python compile 통과. 실제 하드웨어/DDS는 실행하지 않았다.

### 남은 항목

외부 asset bytes와 캡처 당시 모델 binding, 실제 장비 통합 검증은 미완료다.

## 2026-09-06 live 진입점 모델 격리

### 검토

prototype/virtual-center main이 공유 XML을 생성한 뒤 다시 읽었다.
Jog provenance는 별도로 GENERATED_MODEL_PATH 해시를 참조하므로 후속 수정이 필요하다.

### 코드 수정

두 진입점의 생성/로드를 LoadMinkModel로 교체. 공유 XML 갱신 부작용을 제거했다.
기존 _prepare_mink_xml API는 유지. task/solver/operational limits는 변경하지 않았다.

### 테스트

71 passed, 10 subtests passed: logs/test_results/r53_live_model_20260906.xml.
최초 회귀는 기존 _prepare_mink_xml mock 때문에 1건 실패했다. 해당 mock을 제거하여
실제 격리 모델을 사용하게 수정했다. 소켓과 뷰어는 대역으로 유지한다.

### 남은 항목

Jog provenance의 공유 XML 의존 및 캡처 모델 binding. 실제 라이브 장비 검증 미실행.

## 2026-09-06 실제 renderer smoke

### 검토

실제 spawned ProcessRenderer가 임시 모델을 읽는 경로를 검사했다.

### 코드 수정

없음. 기존 생성/renderer API로 로컬 smoke만 실행했다.

### 테스트

640x480 20프레임 모두 렌더링; qpos mismatch/누락 0. 픽셀 변화와 G1 이미지 확인.
자식 프로세스 종료, 임시 XML 제거, 공유 XML 바이트 불변 확인.
logs/test_results/r53_render_smoke_20260906/result.json 및 frame_s16.png.
최초 stdin 실행은 Windows spawn에서 <stdin>을 재실행할 수 없어 실패했다.
-c 실행에서 통과했으며 제품 코드 변경은 없었다.

### 남은 항목

정지 관절과 이동 마커를 20Hz로 전달한 smoke다. 60Hz 성능이나 전체 IK 캡처
재생 결과로 해석하지 않는다. live main/기록 시점 모델 binding은 미완료.

## 2026-09-06 rendered replay 수명 관리

### 검토

LoadReplay와 ProcessRenderer가 공유 DEMO_XML을 따로 읽었다. 기존 R53 범위다.

### 코드 수정

main은 임시 XML을 생성하고 RunReplay가 renderer를 닫은 후 임시 디렉터리를 정리한다.
부모와 자식에 동일 경로를 전달한다. LoadReplay의 기존 3인자 호출은 공통 격리
loader를 사용한다. XML 해시 검사를 유지하고 삭제되는 모델 경로는 null로 기록한다.
planner와 operational limits는 변경하지 않았다.

### 테스트

65 passed: logs/test_results/r53_render_reader_20260906.xml.
실제 MuJoCo 모델 로드 및 렌더러 대역을 통한 성공/생성 실패/재생 실패의 파일
수명을 검사했다. 실제 GPU, spawn 프로세스 또는 전체 캡처 성능 측정은 하지 않았다.

### 남은 항목

실제 렌더 재생과 live main, 캡처 당시 모델/asset binding. R53 partial 유지.

## 2026-09-06 candidate benchmark reader 후속

### 검토

benchmark_mink_candidate도 공유 DEMO_XML을 읽고 해시를 계산했다. 기존 R53에 포함한다.

### 코드 수정

LoadMinkModelWithMetadata로 현재 소스 모델을 생성/로드한다. 기존 기준 보고서의
캡처/모델/엔진/horizon 검사는 유지한다. 보고서의 model_xml_sha256은 실제 생성
XML의 해시이며 model_xml_path=null과 hash_scope가 추가된다. planner는 변경하지 않았다.

### 테스트

격리 및 candidate benchmark 관련 60 passed.
logs/test_results/r53_candidate_reader_20260906.xml.
main의 RunBenchmark는 대체하여 정상 보고서 저장과 네 가지 불일치 중단을 확인했다.
이는 전체 캡처 성능 재측정이나 실제 장비 검증이 아니다.

### 남은 항목

rendered replay는 자식 프로세스에 XML 경로를 전달하므로 파일 수명 관리가 필요하다.
live main 및 캡처 모델/asset binding도 미완료. R53 partial 유지.

## 2026-09-06 return inspection reader 후속

### 검토

inspect_feasible_target_return이 공유 DEMO_XML을 로드하고 해시를 비교했다.
기존 R53 범위이며 새 finding은 추가하지 않았다.

### 코드 수정

현재 소스의 격리 모델과 metadata를 사용한다. 기준 보고서와 캡처/모델 해시가
다르면 기존처럼 중단한다. 결과의 model hash도 실제 로드 모델과 일치시킨다.
과거 모델 해시가 다르면 기존 기준 보고서를 그대로 사용할 수 없다.
IK, operational limits, planner, 렌더링 코드는 변경하지 않았다.

### 테스트

37 passed: logs/test_results/r53_return_reader_20260906.xml.
실제 모델 생성/격리와 main의 정상 보고서 저장, 캡처/모델 불일치 중단 확인.
main 테스트의 캡처 해석과 Run은 대체했으며 전체 재생/렌더링 검증은 아니다.

### 남은 항목

benchmark reader와 live main, 캡처 시점 모델/asset binding은 남아 있다.
R53은 partial 유지. 장비, DDS, WSL, 네트워크 실행 없음.

## 2026-09-06 생성 모델 해시 정합성 후속

### 검토

직전 임시 reader 분리 때 audit_wrist_target_mapping, compare_mink_step_acceptance,
diagnose_mink_distance_invariance의 보고서 해시가 공유 XML을 계속 참조하는
누락이 있었다. 실제 모델과 보고서 식별 정보가 다를 수 있어 R53에서 수정했다.

### 코드 수정

LoadMinkModelWithMetadata가 생성 XML을 로드하기 직전에 SHA256을 계산한다.
기존 LoadMinkModel의 model 단독 반환은 유지하고 세 보고서만 metadata를 받는다.
임시 경로는 삭제되므로 model_xml_path=null이며 모델 출처를 명시한다.
hash_scope는 XML만 포함하고 외부 asset bytes/operational limits는 제외한다.
라이브 main은 아직 변경하지 않았다.

### 테스트

69 passed: 모델 격리, step acceptance, distance invariance.
의도적으로 다른 공유 XML을 둔 상태에서 실제 생성 XML 해시가 사용되는지 확인했다.
결과: logs/test_results/r53_model_hash_20260906.xml

### 남은 항목

전체 CLI 재생/렌더 검증과 캡처 당시 모델·asset binding은 미완료다.
실제 G1/WSL/DDS/네트워크 실행 없음. 이 해시를 물리 실행 허가로 사용하지 않는다.

## 2026-09-06 backend 모델 reader 독립화

### 검토

backend 진단 10곳이 DEMO_XML의 기존 내용에 의존했다. 라이브나 exporter 실행
순서에 따라 숨김/충돌 모델이 달라질 수 있어 R53 범위에서 수정했다.

### 코드 수정

prototype 모듈에 LoadMinkModel을 추가했다. 현재 소스로 임시 모델을 만들고
로드 후 제거한다. 진단 reader 10곳을 연결했으며 기존 operational limit
호출은 그대로다. 기존 _prepare_mink_xml의 공개 호환성과 기본 경로는 유지했다.

### 테스트

격리/가시성/reach 41 passed. reader 10곳의 실제 모델 대입 AST 실행으로 공통
loader 호출을 확인했다. 실제 모델 qpos0/jnt_range/body_pos/geom_pos/mesh_vert
배열 일치, 생성 실패 정리, shared XML 불변, reach main 보고서 저장을 검증했다.
결과: logs/test_results/r53_diagnostic_readers_20260906.xml

### 남은 항목

전체 진단 CLI/렌더/캡처 재생을 실행한 것은 아니다. 현재 소스 모델을 생성하므로
과거 캡처 모델과 동일하다는 증명도 아니다. 캡처 model/asset binding과 라이브
main 및 나머지 reader 점검이 남았다. 실제 장비/네트워크 실행 없음.

## 2026-09-06 라이브 경로 검토 및 캡처 출력 격리

### 검토

라이브 두 제어기는 DEMO_XML을 쓰고 일부 backend 진단 도구는 이를 읽는다.
gate7_mink_capture manifest는 패킷을 기록하지만 XML 모델 binding은 없다.
라이브 경로만 분리하면 reader가 기존 파일을 읽을 수 있어 이번에 변경하지 않았다.
캡처 출력은 초 단위 파일명과 write 모드여서 기존 기록 덮어쓰기가 가능했다.
이는 기존 R53의 writer 범위에 포함한다.

### 코드 수정

자동 캡처 파일명에 UUID를 추가했다. 기존 capture/result 경로는 소켓 생성 전에
거부하고, 둘 다 exclusive create로 기록한다. 파일 존재 확인 이후의 경쟁도
기존 파일을 덮어쓰지 않는다. 패킷 스키마/명령/모델 경로는 변경하지 않았다.

### 테스트

6 passed. 같은 초의 100개 고유 경로, 기존 capture/result, 생성 경쟁 두 경우,
빈 캡처 결과 저장/종료 코드 2를 검사했다. 소켓과 시간은 fake다.
최초 시험의 시간 해상도 의존성을 제거하고 결정적인 mock clock으로 재실행했다.
결과: logs/test_results/r53_capture_outputs_20260906.xml

### 남은 항목

캡처와 결과 두 파일 전체의 원자적 commit은 아니다. 결과 파일 경쟁이 발생하면
캡처만 남을 수 있지만 기존 결과를 덮어쓰지는 않는다. 모델/자산 binding과
라이브 reader 설계는 남았다. 실제 UDP/WSL/G1 실행 없음.

## 2026-09-06 FK export / LowState viewer

### 검토

FK exporter와 live_lowstate_mujoco.LoadModel이 공유 DEMO_XML에 쓰는 경로를
확인했다. 기존 R53이며 라이브 제어기 자체의 모델 경로는 이번 범위에서 제외했다.

### 코드 수정

두 함수는 임시 XML 생성 후 로드하며 이후 임시 파일을 정리한다.
FK 출력 형식/샘플과 viewer 가시성 인자는 유지한다.

### 테스트

격리/가시성 24 passed. LoadModel을 inspection 표시/숨김 양쪽으로 실행하고
socket 생성을 금지했다. FK main은 임시 결과 경로로 실행하여 4개 샘플과
기준 샘플 delta=0을 확인했다. 공통 XML bytes가 변하지 않음을 확인했다.
결과: logs/test_results/r53_viewer_export_20260906.xml

### 남은 항목

viewer UI/실제 LowState 수신은 실행하지 않았다. 라이브 제어기 모델 경로와
캡처 모델/자산 provenance의 연계가 남아 있으며 R53 전체 완료가 아니다.

## 2026-09-06 recovery/editor 후속

### 검토

plan_startup_transition, simulate_startup_recovery, replay_startup_recovery,
edit_startup_ready_pose에서 공통 XML 쓰기가 남아 있어 기존 R53 범위로 수정했다.

### 코드 수정

네 경로를 임시 XML 생성/즉시 로드/정리로 변경했다.
복구 전략, 궤적, 속도, 관절 제한, 저장할 준비 자세는 바꾸지 않았다.

### 테스트

격리/가시성 21 passed. 모델 로드 블록 정상/실패 정리와 공통 XML 불변,
editor CreateModel의 실제 모델 생성 및 지정 관절값 보존을 확인했다.
최초 테스트는 한국어 소스를 CP949로 읽어 6개가 실패했으며 테스트의 읽기
인코딩을 UTF-8로 명시한 후 재실행해 통과했다. 제어 코드를 우회한 것은 아니다.
결과: logs/test_results/r53_recovery_models_20260906.xml

### 남은 항목

전체 복구 계산, 재생 viewer 및 자세 저장 기능은 이번에 실행하지 않았다.
다른 모델 writer와 자산 provenance 검증은 계속 남아 있다. R53 전체 완료 아님.
strategy atlas는 재개하지 않았고 실제 G1/WSL/DDS도 실행하지 않았다.

## 2026-09-06 startup 진단 후속

### 검토

check_startup_readiness의 evaluate_collision_window와
diagnose_initial_pose_collision.main도 공통 XML을 생성했다. 기존 R53 범위다.

### 코드 수정

각 호출의 임시 디렉터리에 모델을 생성하고 로드 후 정리한다.
기존 충돌 쌍/관절 제한/준비 판정 로직은 유지했다.

### 테스트

격리 및 가시성 12 passed. 세 진단 도구의 모델 로드 블록에서 정상/생성 실패
정리를 검증했다. 사전검사 수치 helper는 가상 29축 값으로 실제 충돌 계산을
실행했으며 socket 생성은 테스트에서 금지했다. 공통 XML bytes 불변도 확인했다.
결과: logs/test_results/r53_startup_models_20260906.xml

### 남은 항목

UDP 수신 main, 실제 LowState 입력, G1/WSL/DDS를 실행하지 않았다.
recovery/editor 등 다른 writer와 provenance 검증이 남아 있다.

## 2026-09-06 오프라인 hardware helper 격리

### 검토

verify_initial_pose_sync와 gate7_mink_arm_sdk_offline의 CollisionPathValidator가
공통 DEMO_XML을 생성 후 로드했다. 기존 R53의 남은 writer 범위에 해당한다.

### 코드 수정

두 경로에서 TemporaryDirectory의 model.xml을 생성하고 즉시 로드한다.
로드 후 임시 파일은 제거되며 메모리 모델을 사용한다. 모델 생성 실패에도
임시 디렉터리를 정리한다. 관절 제한/충돌 쌍/출력 명령 계약은 변경하지 않았다.

### 테스트

격리 3개와 기존 모델 가시성 4개: 7 passed.
CollisionPathValidator 두 인스턴스의 서로 다른 경로, 모델 로드/순기구학,
동일 충돌 쌍과 공통 XML bytes 불변을 확인했다. 초기 자세 검증기는 실제 main
전체 대신 모델 로드 블록만 실행해 정상/실패 정리를 검사했다.
결과: logs/test_results/r53_offline_models_20260906.xml

### 남은 항목

startup readiness/recovery/editor 등의 다른 writer와 provenance 검증은 남았다.
실제 캡처 초기화 전체 경로, G1/WSL/DDS/Unity 실행은 하지 않았다.
R53 전체 완료가 아니다.

## 후속: backend 테스트 writer 격리 완료

직접 모델을 생성하던 나머지 backend 테스트 6개를 임시 output_path로 변경했다:
collision diagnostics, feasible target, virtual-center trajectory, orientation policy,
recorded reach bound, Gate7 feedback receiver. 비용/제약/목표/기대값 변경 없음.

`test_mujoco_inspection_scene_visibility`에 backend test 소스를 AST 검사하는
회귀를 추가했다. 모델 생성 호출에 명시적인 output_path가 없거나 None이면 실패한다.
이 검사는 경로가 실제로 임시 경로인지까지 증명하지는 않으므로 소스 검토를 병행한다.

검증: 수치5파일 33 passed/12 subtests, 가시성 및 feedback qpos 5 passed.
합계38 passed/12 subtests. feedback UDP socket 테스트는 이번 실행에서 제외했다.
기존 손목 roll의 음수 거리 실패는 별도 수치검사에 남아 있으며 해결 선언하지 않는다.
R53의 실험 runner 및 모델/자산 provenance는 여전히 미완료다.

## 후속: 손목 실패 분리

R24 후속 검사에서 25도 진폭/12초 사인파 목표의 최대 요구 속도는
약13.1 deg/s임을 확인했다. 현재 cap의 절반 이하가 되도록 주기를 계산한다.
진폭25도와 정확도/근위이동/충돌 기준은 그대로 유지한다. 라이브 설정 변경은 없다.

이 입력에서는 세 손목 축 모두 위치/회전/근위 이동 기준을 통과했다.
하지만 roll의 충돌 거리 검사 한 개는 여전히 실패한다.

- step200, 적분 후3.35초
- right_shoulder_yaw_link와 right_wrist_yaw_link의 collision geom
- 측정 최소거리 -133.20548mm
- 실제 접촉인지 거리 계산의 일관성 문제인지는 미확정

RunCase 결과에 최소거리 발생 step/time/geom_names/qpos를 추가했다.
실패를 숨기거나 양수 거리로 대체하지 않는다. 기존 distance-invariance 조사와
같은 qpos에서 비교할 증거이며 라이브 계층형 IK의 실패로 단정하지 않는다.

후속 수치 검사: 4 passed, 2 subtests passed, 1 subtest failed.
기존 3개 실패가 모두 해결됐다는 뜻이 아니며 충돌 검사를 통과하기 전 채택 불가.

## 검토

R53의 공통 XML 덮어쓰기 경로와 R24의 오래된 속도 기대값을 재확인했다.
기존 미해결 번호를 유지하며 전체 수정 완료로 처리하지 않는다.

## 코드 수정

- `make_demo_xml`과 `_prepare_mink_xml`에 선택적 `output_path`를 추가했다.
  별도 경로를 지정하면 공통 XML을 쓰지 않으며 생성 경로를 반환한다.
  기존 인자 없는 호출은 기존 기본 경로를 유지한다.
- 외부 디렉터리에 생성할 때 mesh/texture 디렉터리를 원본 기준 절대 경로로
  바꿔 MuJoCo가 같은 자산을 찾도록 한다. 현재 원본은 meshdir=meshes이다.
- 카메라 검사, 가시성 검사, virtual-center 수치 회귀검사를 임시 XML로 격리했다.
- 수치 회귀검사의 속도 상한은 고정 40/100이 아닌 현재 helper의 관절별 값을
  검사한다. IK 비용, 충돌 한계, 속도 설정 자체는 변경하지 않았다.

## 테스트

- 관련 10개 pytest 파일: 124 passed, 64 subtests passed.
- 격리된 Mink XML 로딩, collision geom 존재, 공통 XML bytes 불변 확인.
- 변경 Python 파일 5개 compileall 통과.
- 별도 `test_virtual_center_kinematics_regression.py`: 4 passed,
  손목 축별 subtest 3개 실패. 최대 근위 이동 7.77/11.59/24.81도,
  기존 기준은 0.5도 미만이다. 실패 기준을 완화하지 않았다.

## 남은 항목

위 손목 검사는 `RunCase(exact_posture)`의 단일 solve_ik 경로다.
현재 라이브 계층형 QP와 동일한 실행 경로라고 볼 수 없다. R24 검사 전제
재정리 시 단일 QP 기준선과 계층형 경로의 기대치를 분리해 검증해야 한다.
현재 결과만으로 라이브 회귀 원인을 확정하지 않는다.

R53은 부분 수정이다. 다른 공통 XML writer, Recovery evidence의 모델/자산
불변 binding은 남아 있다. 카메라 렌더링/공유메모리 전체 CLI는 실행하지 않았다.
G1/WSL/DDS/Unity 또는 물리 출력은 실행하지 않았다.
