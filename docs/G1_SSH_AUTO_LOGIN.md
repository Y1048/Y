> Current integrated launcher only uses SSH for camera. It does not start/reuse the audit receiver. Older receiver enrollment descriptions below are historical.

# G1 자동 SSH 로그인

`tools/START_G1_VR_TELEOP.bat` 실행 시 새 수신기를 시작하기 전에 해당 PC의 키 로그인을 확인한다. 처음 사용하는 PC에서는 실행창에 G1 비밀번호를 한 번 입력한다. 성공하면 이후 실행은 자동 로그인한다. 비밀번호를 BAT, Python, 로그, GitHub에 저장하지 않는다.

PC의 Windows 사용자별 `%USERPROFILE%/.ssh/id_ed25519_g1_teleop` 및 `.pub`를 사용한다. 무인 로그인을 위한 암호 없는 전용 키이며 개인키는 해당 PC에만 둔다. 다른 PC에서는 각자 새 키를 생성하고 등록한다. G1에는 공개키만 `~/.ssh/authorized_keys`에 추가하며 기존 항목을 보존한다.

새 주소의 호스트 키는 첫 접속 시 OpenSSH accept-new로 저장한다. 기존 호스트 키가 달라지면 거부하며 자동 삭제하지 않는다. 키 등록 뒤 BatchMode로 실제 로그인을 검증하고 실패하면 입력 프로세스 실행 전에 종료한다. G1이 꺼져 있거나 연결이 안 되면 등록되지 않는다.

`--check-only`는 키 생성, 등록, SSH 로그인을 하지 않는다. `--no-receiver` 또는 기존 수신기 재사용도 등록을 생략한다. `START_G1_INPUT_OBSERVATION` 단독 실행은 자동 등록을 제공하지 않으며 등록된 키 사용 또는 기존 SSH 프롬프트로 동작한다.

문제 발생 시 `.ssh` 키/known_hosts를 임의 삭제하지 말고 출력된 오류를 확인한다. 키 파일은 GitHub나 다른 PC로 복사하지 않는다.

검증: 오프라인 테스트 36개 및 subtest 41개 통과. 실제 G1 등록/자동 로그인은 미검증이며 다음 연결 실행에서 진행한다. 로봇 제어기/SDK/DDS/모터는 실행하지 않았다.
