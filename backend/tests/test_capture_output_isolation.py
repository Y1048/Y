"""Capture output reservation tests using fake sockets only."""
import json
import itertools
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "hardware/g1_arm_bridge"))
import gate7_mink_capture as capture


def test_same_second_names_are_unique(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "CAPTURE_DIRECTORY", tmp_path)
    monkeypatch.setattr(capture.time, "strftime", lambda _: "fixed")
    paths = {capture._automatic_path() for _ in range(100)}
    assert len(paths) == 100
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("scenario", ["capture_exists", "result_exists", "capture_race", "result_race", "new"])
def test_existing_outputs_never_overwritten(tmp_path, monkeypatch, scenario):
    output = tmp_path / "capture.jsonl"
    result = output.with_suffix(".result.json")
    protected = output if scenario.startswith("capture") else result
    if scenario.endswith("exists"):
        protected.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(capture, "_parse_args", lambda: SimpleNamespace(
        listen_host="127.0.0.1", forward_host="127.0.0.1",
        listen_port=5008, forward_port=5014, duration_s=1e-12, output=output))
    sockets = []
    ticks = itertools.count()
    monkeypatch.setattr(capture.time, "monotonic", lambda: float(next(ticks)))

    class FakeSocket:
        closed = False

        def bind(self, endpoint):
            if scenario.endswith("race"):
                protected.write_text("previous", encoding="utf-8")

        def settimeout(self, timeout):
            pass

        def recvfrom(self, size):
            raise AssertionError("loop should have expired")

        def close(self):
            self.closed = True

    def socket_factory(*args):
        assert not scenario.endswith("exists"), "existing files must block before sockets"
        instance = FakeSocket()
        sockets.append(instance)
        return instance

    monkeypatch.setattr(capture.socket, "socket", socket_factory)
    if scenario == "new":
        assert capture.main() == 2  # No received packets is not a successful recording.
        assert json.loads(result.read_text())["accepted_packets"] == 0
        assert json.loads(output.read_text())["schema"] == "g1.mink.capture.manifest.v1"
    else:
        with pytest.raises(FileExistsError):
            capture.main()
        assert protected.read_text() == "previous"
    assert all(sock.closed for sock in sockets)
