"""Build a local source inventory without importing or running project modules.

Run from any directory with Python 3.11. --check detects a stale index.
Only docs/CODE_INDEX.md is written; no SDK, socket, or robot access is used.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (
    "backend", "hardware", "experiments", "tools", "config",
    "MuJoCo_G1_Controller/scripts", "Unity_G1_VR/Assets/G1Teleop",
    "Unity_G1_VR/Assets/Editor",
)
EXTENSIONS = {".py", ".cs", ".cpp", ".hpp", ".h", ".bat", ".ps1", ".sh", ".json", ".toml", ".yaml", ".yml"}
EXCLUDED = {"__pycache__", "build", ".venv", "venv", "node_modules", "third_party", ".git"}
# Boundary review is not a claim that every function was audited.
BOUNDARY_REVIEWED = {
    "START_VR_HAND_TO_MUJOCO.bat",
    "tools/SET_UNITY_DISPLAY_MODE.ps1",
    "MuJoCo_G1_Controller/scripts/run_mink_g1_right_arm_virtual_center_live.py",
    "MuJoCo_G1_Controller/scripts/g1_mink_feasible_target.py",
    "backend/g1_teleop/mink_command_stream.py",
    "backend/g1_teleop/live_receiver.py",
    "backend/g1_teleop/command_adapter.py",
    "hardware/g1_arm_bridge/gate7_mink_wsl_relay.py",
    "hardware/g1_arm_bridge/gate7_live_arm_sdk.py",
    "Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs",
    "Unity_G1_VR/Assets/G1Teleop/G1ExistingTargetUdpSender.cs",
    "Unity_G1_VR/Assets/G1Teleop/G1RobotStateUdpReceiver.cs",
    "Unity_G1_VR/Assets/G1Teleop/G1UnityRightArmPreview.cs",
}


def CollectFiles(root: Path) -> list[Path]:
    paths = {p for p in root.iterdir() if p.is_file() and p.suffix in EXTENSIONS}
    for relative in SOURCE_ROOTS:
        directory = root / relative
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if (path.is_file() and path.suffix in EXTENSIONS
                    and not EXCLUDED.intersection(path.relative_to(root).parts)):
                paths.add(path)
    return sorted(paths, key=lambda p: p.relative_to(root).as_posix())


def GetPythonSymbols(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "구문 분석 실패"
    names = [node.name for node in tree.body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    shown = ", ".join(names[:5]) or "-"
    return shown + (f" (+{len(names) - 5})" if len(names) > 5 else "")


def BuildIndex(root: Path) -> str:
    paths = CollectFiles(root)
    lines = [
        "# 코드 파일 색인", "",
        "[읽기 순서와 연결 관계](CODE_GUIDE.md) | [시스템 구조](ARCHITECTURE.md)", "",
        "이 목록은 지정된 프로젝트 코드/설정 폴더를 자동 열거한 결과다.",
        "**파일을 목록에 넣었다는 것과 내용을 끝까지 검토했다는 것은 다르다.**", "",
        "- `입출력 확인`: 입출력·호출 경로의 주요 부분 확인. 전체 함수 검토 완료가 아니다.",
        "- `목록 확인`: 파일 존재·줄 수·선언만 수집. 기능 설명과 세부 검토는 남아 있다.",
        "- Python 선언은 AST로 추출하며 C#/C++/배치의 호출 그래프를 자동 추정하지 않는다.",
        "- 상태는 2026-09-03 확인 범위다. 이후 변경은 다시 검토해야 한다.", "",
        f"대상 파일: **{len(paths)}개**. 해시 앞 12자리는 검토 시점 파일 비교용이다.", "",
        "## 포함 범위", "",
        "루트 실행 파일과 다음 폴더의 코드/설정 파일:", "",
        *[f"- `{folder}`" for folder in SOURCE_ROOTS], "",
        "원본 `references`, 로그·캡처, 로봇 mesh/XML, Unity 씬/prefab/meta,",
        "외부 SDK·Packages·Library·빌드 산출물은 이 코드 색인에서 제외한다.",
        "제외 항목을 미사용 또는 검토 완료로 판정한 것은 아니다.", "",
        "## 갱신", "", "```powershell",
        "py -3.11 backend/tools/build_code_index.py",
        "py -3.11 backend/tools/build_code_index.py --check", "```", "",
        "## 파일 목록", "",
        "| 파일 | 줄 수 | 상태 | Python 최상위 선언(최대 5개) | SHA256 앞 12자리 |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for path in paths:
        relative = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        source = raw.decode("utf-8-sig")
        status = "입출력 확인" if relative in BOUNDARY_REVIEWED else "목록 확인"
        symbols = GetPythonSymbols(source) if path.suffix == ".py" else "-"
        digest = hashlib.sha256(raw).hexdigest()[:12]
        link = quote("../" + relative, safe="/._-")
        lines.append(f"| [{relative}]({link}) | {len(source.splitlines())} | {status} | {symbols} | `{digest}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "docs" / "CODE_INDEX.md"
    content = BuildIndex(ROOT)
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != content:
            print("[FAIL] Code index is stale. Run: py -3.11 backend/tools/build_code_index.py")
            return 1
        print("[PASS] Code index matches current scoped source files.")
    else:
        output.write_text(content, encoding="utf-8")
        print(f"Saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
