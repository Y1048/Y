"""Offline-only renderer process with one bounded, coherent latest-state slot."""

import json
import hashlib
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
from PIL import Image

from benchmark_mink_rendered_replay import ReplayRenderer, comparison, SummarizeTiming


class LatestStateSlot:
    def __init__(self, context, nq):
        if nq < 1:
            raise ValueError("Positive qpos size required")
        self.nq = nq
        self.values = context.RawArray("d", nq + 8)
        self.lock = context.Lock()

    def Publish(self, sequence, timestamp, q, goal, preview):
        if np.shape(q) != (self.nq,) or np.shape(goal) != (3,) or np.shape(preview) != (3,):
            raise ValueError("Invalid snapshot field sizes")
        values = np.concatenate(([sequence, timestamp], q, goal, preview))
        if (values.shape != (self.nq + 8,) or not np.isfinite(values).all()
                or sequence < 1 or sequence >= 2**53 or sequence != int(sequence)):
            raise ValueError("Invalid state snapshot")
        if not self.lock.acquire(False):
            return False
        try:
            if sequence <= self.values[0]:
                return False
            np.frombuffer(self.values, dtype=np.float64)[:] = values
            return True
        finally:
            self.lock.release()

    def ReadAfter(self, sequence):
        if not self.lock.acquire(False):
            return None
        try:
            if self.values[0] <= sequence:
                return None
            return np.frombuffer(self.values, dtype=np.float64).copy()
        finally:
            self.lock.release()


def RunRenderWorker(slot, stop, connection, model_path, initial, width, height,
                    trace_path, snapshot_prefix, stall_ms):
    renderer = None
    try:
        probe = comparison.probe
        model = probe.mujoco.MjModel.from_xml_path(model_path)
        probe.base._apply_operational_joint_limits(model)
        expected = [json.loads(line)["qpos"] for line in Path(trace_path).read_text(encoding="utf-8").splitlines()]
        renderer = ReplayRenderer(model, width, height)
        for _ in range(10):
            renderer.Draw(initial, [0., 0., 1.], [0., 0., 1.])
        connection.send({"status": "READY", "engine": probe.mujoco.__version__})
        samples, snapshots = [], {}
        last = skipped = changes = mismatches = injected_stalls = 0
        minimum_std = float("inf")
        previous_pixels = None
        while True:
            state = slot.ReadAfter(last)
            if state is None:
                if stop.is_set():
                    break
                time.sleep(.001)
                continue
            sequence = int(state[0])
            timestamp = state[1]
            start = time.perf_counter()
            if timestamp > start or sequence > len(expected):
                raise ValueError("Snapshot clock or sequence outside replay")
            q = state[2:2 + model.nq]
            if not np.array_equal(q, expected[sequence - 1]):
                mismatches += 1
            skipped += sequence - last - 1
            last = sequence
            if stall_ms and len(samples) % 120 == 119:
                time.sleep(stall_ms / 1000)
                injected_stalls += 1
            pixels = renderer.Draw(q, state[-6:-3], state[-3:])
            finish = time.perf_counter()
            small = pixels[::16, ::16].copy()
            minimum_std = min(minimum_std, float(small.std()))
            changes += int(previous_pixels is not None and not np.array_equal(previous_pixels, small))
            previous_pixels = small
            # Save representative frames after the timed rendering has finished.
            bucket = min(3, (sequence - 1) * 4 // len(expected))
            if bucket not in snapshots:
                snapshots[bucket] = (sequence, pixels.copy())
            samples.append({"sequence": sequence, "source_age_start_ms": (start - timestamp) * 1000,
                "source_age_finish_ms": (finish - timestamp) * 1000, "render_work_ms": (finish - start) * 1000})
        if not samples:
            raise RuntimeError("Renderer received no measured states")
        paths = []
        for sequence, pixels in snapshots.values():
            path = Path(f"{snapshot_prefix}_s{sequence}.png")
            Image.fromarray(pixels).save(path)
            paths.append(str(path.resolve()))
        result = {"status": "COMPLETE", "frames_rendered": len(samples), "last_sequence": last,
            "skipped_sequences": skipped, "state_qpos_mismatches": mismatches, "injected_stalls": injected_stalls,
            "timings": {key: SummarizeTiming([s[key] for s in samples], 1000 / 60)
                        for key in ("source_age_start_ms", "source_age_finish_ms", "render_work_ms")},
            "render_check": {"minimum_sampled_pixel_std": minimum_std, "changed_frames": changes,
                             "nonblank_and_changing": minimum_std > 5 and changes > 0},
            "screenshots": paths,
            "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "post_stall_frames": [s for i, s in enumerate(samples)
                                  if stall_ms and i > 0 and i % 120 == 0],
            "stale_over_50ms_frames": [s for s in samples if s["source_age_finish_ms"] > 50]}
        connection.send(result)
    except BaseException as error:
        connection.send({"status": "ERROR", "error": f"{type(error).__name__}: {error}"})
    finally:
        if renderer is not None:
            renderer.Close()
        connection.close()


class ProcessRenderer:
    is_async = True

    def __init__(self, model_path, initial, width, height, trace_path, snapshot_prefix, stall_ms=0):
        context = mp.get_context("spawn")
        self.slot = LatestStateSlot(context, len(initial))
        self.stop = context.Event()
        self.connection, writer = context.Pipe(duplex=False)
        self.process = context.Process(target=RunRenderWorker, args=(self.slot, self.stop, writer,
            str(model_path), initial, width, height, str(trace_path), str(snapshot_prefix), stall_ms))
        self.active = False
        self.sequence = self.busy_drops = 0
        self.result = None
        self.process.start()
        writer.close()
        try:
            ready = self.Receive(30)
            if ready["status"] != "READY" or ready["engine"] != comparison.probe.mujoco.__version__:
                raise RuntimeError(f"Renderer startup failed: {ready}")
        except BaseException:
            self.Close()
            raise

    def Receive(self, timeout):
        if not self.connection.poll(timeout):
            raise TimeoutError("Offline render worker did not respond")
        return self.connection.recv()

    def BeginRun(self):
        self.active = True

    def Draw(self, q, goal, preview):
        if not self.active:
            return None
        if not self.process.is_alive():
            raise RuntimeError("Offline render worker exited during replay")
        self.sequence += 1
        if not self.slot.Publish(self.sequence, time.perf_counter(), q, goal, preview):
            self.busy_drops += 1
        return None

    def FinishRun(self):
        self.active = False
        self.stop.set()
        self.result = self.Receive(20)
        self.process.join(5)
        if self.result["status"] != "COMPLETE" or self.process.exitcode != 0:
            raise RuntimeError(f"Offline renderer failed: {self.result}")
        self.result["producer_states"] = self.sequence
        self.result["producer_busy_drops"] = self.busy_drops
        self.result["trailing_unrendered_states"] = self.sequence - self.result["last_sequence"]
        return self.result

    def Close(self):
        self.stop.set()
        if self.process.is_alive():
            # Drain a possible final report so the child's pipe send cannot block join.
            if self.result is None and self.connection.poll(5):
                try:
                    self.connection.recv()
                except (EOFError, OSError):
                    pass
            self.process.join(5)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(5)
        self.connection.close()
