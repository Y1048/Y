# Windows Player 빌드 검증 — 2026-10-07

기존 Quest Link → Windows Unity → PC Mink/Omni 구조를 유지한 Windows64 빌드를 만들었다.
APK 전환이나 hand-tracking/IK/송신/PD 변경은 하지 않았다.
Unity Editor 6000.5.4f1의 `G1VRBuild.BuildWindows`로 isolated worktree에서 빌드했다.
시작 당시 씬·package manifest·Player 설정·빌드 스크립트는 Portable과 바이트 동일했다.
사용자가 열어 둔 Portable Unity Editor/Play 상태를 변경하지 않았다.

## 결과

- build success, Unity batch exit 0.
- 후보: `C:\Users\user\Desktop\G1_Teleop_Portable\Builds\Windows_candidate_20261007\G1Teleop.exe`
- 파일 231개, 총 243,612,889 bytes. exe만 복사하면 안 되며 폴더 전체를 전달해야 한다.
- exe SHA256: `e8bb8f9dfe2a039ce0b2123da1b65f48fe68ff838147361b468a559f43a27a66`.
- 실제 빌드에 주입된 DevAgent 토큰·주소가 resources.assets에 남지 않음을 확인했다.
- 플레이어 실행, Quest 실착 hand tracking, engage/pinch, 실제 G1 입력·모터 검증은 아직 하지 않았다.
- 이 폴더는 Unity Player만이다. PC Mink/Omni/카메라·Python 환경까지 포함한 최종 배포 패키지는 아니다.

## 빌드 중 발견한 문제와 수정

Meta SDK `DevAgentBuildProcessor`는 callbackOrder 1에서 메모리의 RuntimeSettings에
현재 PC 주소·토큰을 넣고, postprocess에서 원래 값으로 복구한다. 기존 sanitizer는
BuildPlayer가 반환한 뒤 YAML의 복구된 값을 읽었다. 이 PC에서는 build에 들어간 주소와
복구된 주소가 달라 exact occurrence count 0으로 fail-closed 중단했다.

`G1WindowsBuildResourceCapture`가 마지막 preprocess에서 SerializedObject의 실제 값들을
캡처하고 sanitizer가 그 값으로 검사하게 수정했다. token/address property가 없거나
capture hook이 실행되지 않으면 거부한다. 1회 존재→동일 길이 치환→존재 0 검사는 유지했다.
누락·중복을 허용하거나 SDK package 원본을 수정하지 않았다. YAML helper의 whitespace도
빈 값 뒤 다음 줄을 삼키지 않도록 수평 whitespace로 제한했다.

초기 Meta Audio `UnityEditor.GUID` 오류는 Unity API Updater가 자동 수정 후 재컴파일했다.
SDK/package 코드를 수동 수정하지 않았다. 첫 실패의 log/artifact는 삭제하지 않았다.
첫 실패 출력은 배포하지 않았으며 성공한 retry만 별도 Portable 후보 폴더로 복사했다.

## 실행한 검사와 한계

실제 Unity Windows64 build 성공 및 batch exit 0, exe hash sidecar 대조,
실제 resources.assets token·주입 address 제거 확인을 수행했다.
실제 C# sanitizer helper를 Windows .NET Framework compiler로 추출·컴파일·실행하여
단일 값 제거, 누락/중복 거부, 빈 값 유지, YAML 줄 경계, UTF8 값 제거를 확인했다.
이는 runtime hand tracking 검사가 아니다. Quest Link와 같은 XR 환경에서 실제 입력 확인이 남았다.

local evidence: `logs/test_results/builds_20261007/`의 `unity_windows.log`,
`unity_windows_retry.log`, `windows_verified.json`, `sanitizer_fixture.log`.
빌드 과정 SDK가 isolated worktree의 DevAgentSettings/ProjectSettings/TagManager를 자동 갱신했지만
그 파일들은 커밋하지 않는다. 원래 source dirty DevAgentSettings와 Portable 프로젝트는 보존했다.

동시에 G1 관찰 hook의 ARM 통합 컴파일도 별도 디렉터리에서 완료했다.
상세 결과: `GROOT_ARM_COMMAND_OBSERVER_20261007.md`. 후보 바이너리 실행/교체는 하지 않았다.
