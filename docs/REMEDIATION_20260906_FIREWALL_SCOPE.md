# R57 LowState 방화벽 범위

## 검토

기존 규칙은 RemoteAddress=LocalSubnet, interface 제한 없음이었다.
G1 Ethernet 외의 Wi-Fi 등 다른 서브넷에서도 UDP 5007/5009 접근을 허용했다.
R57의 기존 finding에 해당하며 새 번호를 만들지 않았다.

## 코드 수정

- G1용 ASIX AX88772A 어댑터 한 개만 선택. 복수이면 중단하고
  명시적 -InterfaceIndex를 요구한다. 다른 종류/없는 index도 중단한다.
- InterfaceAlias와 RemoteAddress=192.168.123.0/24를 함께 제한한다.
  Profile Any는 해당 전용 interface의 네트워크 프로필 변경을 허용하기 위해
  유지하지만 다른 interface/subnet은 허용하지 않는다.
- 변경 전 기존 완료 표식을 제거하고, 새 규칙 생성 성공 후에만 표식을 쓴다.
- BAT 실패 안내를 권한 승인 반복 대신 어댑터/범위 확인 안내로 변경했다.

## 테스트

실제 Get-NetAdapter와 firewall/file mutation을 모두 PowerShell 함수로 대체했다.
0개/2개 어댑터 자동선택 거부, 1개 선택, 복수에서 명시적 선택, 없는 index 거부:
5 passed. rule 생성 인수(interface/subnet/UDP ports)를 검사했다.
logs/test_results/r57_firewall_scope_20260906.xml 참조.

초기 테스트 harness는 실행 정책 때문에 스크립트에 도달하지 못했고,
이후 script scope 때문에 모의 결과를 수집하지 못했다. 해당 프로세스에만
Bypass와 모의 상태 수집을 적용했다. 시스템 실행 정책은 변경하지 않았다.

## 남은 항목

실제 방화벽/네트워크 설정은 변경하지 않았다. R57은 source 수정 완료이며
WSL 전달 패킷의 실제 ingress interface/source 호환성은 검증하지 않았다.
NAT/다른 WSL 경로가 필요하면 그 경로를 확인해 별도 최소 범위 규칙을 검토한다.
G1 동작, DDS 통신, 사용자 권한 상승을 실행하지 않았다.
R58 후속 수정 결과는 아래에 기록한다.

# R58 LowState 규칙 실패 복구

## 검토

기존 규칙을 먼저 삭제하면 생성 실패 시 이전 규칙까지 잃었다.
R58 범위를 확장했으며 새로운 finding 번호를 만들지 않았다.

## 코드 수정

- PersistentStore의 동일 이름 규칙과 변경 대상 필터를 먼저 읽는다.
- 기존 규칙은 삭제하지 않고 Set-NetFirewallRule로 갱신한다.
  수정하지 않는 program/service 필터와 표시 이름은 유지한다.
- 변경한 모든 필드를 다시 읽어 검증한 후 완료 표식을 기록한다.
- 변경/검증/표식 저장 실패 시 이전 필드를 복구하고 재검증한다.
  새로 만든 규칙이라면 제거하고 규칙이 없는 상태로 복구한다.
- 복구까지 실패하면 ROLLBACK FAILED로 알리며 성공으로 처리하지 않는다.

## 테스트

PowerShell 외부 cmdlet과 파일 작업을 모두 mock한 15 cases passed.
어댑터 선택, 신규/기존 규칙 성공, 부분 쓰기 실패, 적용값 불일치,
표식 저장 실패, 복구 실패, 최초 snapshot 실패를 포함한다.
기존 Program 값 보존과 완료 표식 제거도 확인했다.
결과: logs/test_results/r58_firewall_rollback_20260906.xml

## 남은 항목

위 배치는 LowState 규칙에만 적용된다. DDS 후속 배치는 아래에 기록한다.
Ethernet/DNS 복구는 아직 R58의 남은 범위다. 실제 관리자 실행, GPO 유효 정책, WSL ingress는
검증하지 않았다. 프로세스 강제 종료/전원 단절 및 외부의 동시 규칙 변경까지
원자적으로 복구하는 기능은 아니다. 복구 실패 메시지가 나오면 재실행 전에
해당 로컬 규칙을 직접 확인해야 한다. G1/WSL/실제 방화벽은 변경하지 않았다.

# R58 DDS 규칙 쌍 복구

## 검토

Hyper-V 규칙 생성 후 Host 규칙 생성이 실패하면 중간 상태가 남았다.
R58에 해당하며 새 번호는 추가하지 않았다. ASIX 첫 항목 임의 선택도 확인했다.

## 코드 수정

ALLOW_G1_DDS_WSL_ADMIN.ps1은 두 규칙을 변경 전에 모두 snapshot한다.
기존 규칙은 직접 갱신하고 변경한 필드를 재검증한다. 신규 규칙만 생성한다.
두 번째 규칙이나 완료 표식 저장이 실패하면 역순으로 이전 상태를 복구한다.
한 규칙 복구가 실패해도 나머지 복구를 시도하고 ROLLBACK FAILED로 보고한다.
복수 ASIX는 -InterfaceIndex를 요구한다. Any 프로토콜/서브넷 범위는 유지했다.
BAT 오류 안내도 복구 실패 시 두 규칙을 먼저 확인하도록 수정했다.

## 테스트

DDS 32개 + 기존 LowState 15개 = 47개 모의 테스트.
두 규칙 존재 여부 4조합, 각 규칙 부분 쓰기 실패, 검증 실패, 표식 저장 실패,
복구 실패, 두 번째 snapshot 실패, 어댑터 선택을 검증한다.
Any/256 및 GUID 중괄호 표현 차이도 동등하게 비교한다.
결과: logs/test_results/r58_dds_rollback_20260906.xml

## 남은 항목

R58 Ethernet/DNS 복구가 남았다. 실제 방화벽, WSL, G1은 변경하지 않았다.
GPO/Hyper-V 실제 적용 및 ingress 검증은 별도이며 강제 종료/동시 외부 변경에
대한 원자성은 제공하지 않는다. 이 테스트는 네트워크 통신 성공 증명이 아니다.

# R58 IPv4 DNS 변경 경계

## 검토

CONFIGURE/RESTORE 스크립트는 InterfaceIndex만으로 DNS 전체를 reset했다.
이번 배치는 IPv4 DNS에만 한정하고 DNS 실패를 복구한다. R58의 부분 수정이다.

## 코드 수정

- G1_ETHERNET_DNS.ps1에서 adapter GUID에 해당하는 IPv4 NameServer를 읽는다.
  registry는 읽기만 한다. 빈 값은 자동 모드, 값이 있으면 수동 서버 순서로 저장한다.
- 두 스크립트 모두 IP 변경 전에 snapshot을 읽는다. 읽기 실패 시 IP 변경도 하지 않는다.
- IPv4 최종 검증 후 IPv4 DNS client 객체만 Set-DnsClientServerAddress에 전달한다.
  IPv6 DNS 객체는 선택하거나 변경하지 않는다.
- reset 결과의 수동 override 제거를 확인한다. 실패 시 원래 자동/수동 모드로
  복구하고 재검증한다. 복구 실패는 DNS ROLLBACK FAILED로 보고한다.

## 테스트

DNS 12개 및 기존 diagnostic exit contract 91개, 총 103 passed.
자동/수동 모드의 정상 reset, 부분 쓰기 실패, 검증 실패, 복구 실패,
snapshot 실패와 IP 변경 전 snapshot/검증 후 reset 순서를 확인했다.
cmdlet과 registry 읽기는 mock이다. 기존 테스트의 파일 작업은 임시 폴더에 한정했다.
결과: logs/test_results/r58_dns_20260906.xml

## 남은 항목

이것은 전체 Ethernet transaction rollback이 아니다. DNS 변경 실패 전에 IP가
바뀌었다면 DNS만 복구된다. DHCP lease/route 복구 및 마지막 표식 쓰기 실패까지
포함하는 전체 복구는 다음 범위다. 실제 registry/provider 표현과 정책 적용도
아직 확인하지 않았다. DNS 자동 모드 확인은 DHCP DNS 수신/이름 해석 성공의
증명이 아니다. 실제 G1/WSL/관리자 네트워크 작업은 실행하지 않았다.

# R58 Ethernet 구성 복구

## 검토

DNS 자체가 복구되어도 앞서 변경한 IP가 남았다. 마지막 완료 파일 저장 실패도
동일했다. DHCP 임대값은 수동 주소처럼 재생하면 안 되므로 복구 범위를 구분했다.

## 코드 수정

G1_ETHERNET_TRANSACTION.ps1을 두 관리자 스크립트가 공통 사용한다.
ActiveStore/PersistentStore의 DHCP 모드와 영구 수동 IPv4 주소 및 DNS를
변경 전에 저장한다. 설정 변경/검증/DNS/완료 파일 쓰기 실패 시 복구한다.
수동 주소의 prefix/SkipAsSource를 보존하고 양쪽 store를 재검증한다.
복구 실패는 ROLLBACK FAILED로 보고하며 stale 완료 표식을 남기지 않는다.
복구 중 interface index가 다른 장치로 바뀌면 GUID 확인으로 변경을 차단한다.

지원 조건은 두 store의 모드/수동 주소가 같고 경로가 Local/Dhcp로 관리되는 경우다.
사용자 지정 경로, 임시 수동 주소, store 불일치는 변경 전에 중단한다.
경로를 임의로 삭제/복원하지 않는다. DHCP 복구는 자동 모드 복원이며 같은
임대 주소/기본 경로의 즉시 재확보를 뜻하지 않는다. 정적 설정 검증에서는
예상 외 DHCP/자동 주소가 남아도 성공 처리하지 않는다.

## 테스트

Ethernet 28 + DNS/기존 진단 103 = 131 passed.
정적/자동 초기 상태와 정적/DHCP 목적 상태의 조합, 중간 쓰기/DNS/표식 실패,
복구 실패, 사용자 지정 경로/store 불일치의 사전 차단을 검증했다.
모든 네트워크/registry cmdlet은 mock이며 실제 장치 설정을 바꾸지 않았다.
결과: logs/test_results/r58_ethernet_20260906.xml

## 남은 항목

Windows의 실제 store 간 반영, address provider 수명 표현, DHCP 재확보는
미검증이다. 원자적 OS transaction이 아니며 프로세스 강제 종료/전원 단절이나
외부의 동시 변경까지 복구하지 않는다. 사용자 지정 경로는 자동 복구 대신
사전 차단한다. 승인 없이 관리자 스크립트를 실행하지 않았다.
