"""Robot-offline MuJoCo comparison: project hierarchy and standard Mink 6D QP."""

import argparse
import json
import math
from pathlib import Path
from queue import SimpleQueue
import tempfile
import time

import numpy as np
import glfw

from verify_feasible_target import BuildPlanner, probe


CASES = ("wrist X", "wrist Y", "wrist Z", "position", "combined", "toward body",
         "3D figure eight", "reach and turn", "inspection sweep", "fixed hand multi-axis turn")
CONTROL_HELP = "F8 view | F9 motion | F10 restart | F11 speed | F12 pause"
PLAYBACK_SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)


def NextPlaybackSpeed(speed):
    return next((value for value in PLAYBACK_SPEEDS if value > speed), PLAYBACK_SPEEDS[0])


def GetCompositeGoal(case, seconds):
    phase = 2 * math.pi * seconds / 20.0
    envelope = math.sin(phase / 2) ** 2
    if case == 6:
        delta = envelope * np.array([.07 * math.sin(phase), .10 * math.sin(2 * phase), .10 * math.cos(phase)])
        angles = envelope * np.array([.35 * math.sin(phase), .45 * math.cos(phase), .3 * math.sin(2 * phase)])
    elif case == 7:
        delta = envelope * np.array([.12, -.07 * math.cos(phase), .10])
        angles = envelope * np.array([.4, .5 * math.sin(phase), -.4])
    elif case == 8:
        delta = envelope * np.array([.06, .12 * math.sin(phase), .09 * math.sin(2 * phase)])
        angles = envelope * np.array([.25 * math.sin(2 * phase), .35, .45 * math.sin(phase)])
    elif case == 9:
        delta = np.zeros(3)
        angles = envelope * np.array([.6 * math.cos(phase), .45 * math.sin(phase), .4 * math.sin(2 * phase)])
    else:
        raise ValueError("Not a composite case")
    rotation = (probe.mink.SO3.from_x_radians(angles[0]) @
                probe.mink.SO3.from_y_radians(angles[1]) @
                probe.mink.SO3.from_z_radians(angles[2])).as_matrix()
    return delta, rotation


def HandleComparisonKey(key, simulation, case, selected, paused):
    if key == glfw.KEY_F8:
        selected = 1 - selected
    elif key == glfw.KEY_F9:
        case = (case + 1) % len(CASES)
        simulation.Reset()
    elif key == glfw.KEY_F10:
        simulation.Reset()
    elif key == glfw.KEY_F12:
        paused = not paused
    return case, selected, paused


class RecordedPlayback:
    """Select stored fixed-dt states by wall time; playback never calls the IK solver."""
    def __init__(self, simulation, duration):
        self.simulation = simulation
        self.model = simulation.model
        self.duration = duration
        self.cache = {}
        self.frames = []
        self.q, self.goal, self.rows, self.seconds = simulation.q, simulation.goal, [], 0.0

    def Prepare(self, case, progress):
        if case not in self.cache:
            self.simulation.Reset()
            frames = []
            count = math.ceil(self.duration / probe.base.DT)
            for index in range(count):
                self.simulation.Step(case)
                frames.append((np.array(self.simulation.q).copy(),
                               self.simulation.goal, [dict(row) for row in self.simulation.rows],
                               self.simulation.seconds))
                if index % 10 == 0 or index == count - 1:
                    progress(index + 1, count)
            self.cache[case] = frames
        self.frames = self.cache[case]
        self.Reset()

    def Reset(self):
        self.cursor = 0.0
        if self.frames:
            self.ShowFrame()

    def ShowFrame(self):
        index = min(int(self.cursor / probe.base.DT), len(self.frames) - 1)
        self.q, self.goal, self.rows, self.seconds = self.frames[index]

    def Advance(self, elapsed, speed, paused):
        if not paused:
            self.cursor = min(self.cursor + max(0., elapsed) * speed,
                              (len(self.frames) - 1) * probe.base.DT)
        self.ShowFrame()


class Comparison:
    def __init__(self, model, profile):
        self.model = model
        self.profile = profile
        self.initial = probe.base._initial_configuration(model)
        addresses = [int(model.jnt_qposadr[probe.base._joint_id(model, name)])
                     for name in probe.base.g1.RIGHT_ARM_JOINTS]
        self.initial[addresses] = np.deg2rad([10, -22, 0, 55, 0, 0, 0])
        self.config = probe.mink.Configuration(model)
        self.config.update(self.initial)
        pose = self.config.get_transform_frame_to_world("right_wrist_yaw_link", "body")
        self.origin = pose.translation().copy()
        self.rotation = pose.rotation().as_matrix().copy()
        self.wrist = probe.mink.FrameTask("right_wrist_yaw_link", "body",
            probe.base.POSITION_COST, probe.base.ORIENTATION_COST,
            gain=probe.base.FRAME_GAIN, lm_damping=probe.base.LM_DAMPING)
        posture = probe.mink.PostureTask(model, cost=probe.base.POSTURE_COST)
        posture.set_target(self.initial)
        damping = probe.mink.DampingTask(model, cost=probe.base._damping_costs(model))
        self.tasks = [self.wrist, posture, damping]
        self.Reset()

    def Reset(self):
        self.planner = BuildPlanner(self.model, self.initial, collision_profile=self.profile)
        self.q = [self.initial.copy(), self.initial.copy()]
        self.seconds = 0.0
        self.joint_travel = np.zeros((2, 7))
        self.rejected_steps = 0
        self.rows = []
        self.goal = probe.base._matrix_to_se3(self.rotation, self.origin)

    def Step(self, case):
        # Slow analytic input, identical wrist-yaw pose requested from both solvers.
        wave = math.sin(math.pi * self.seconds / 20.0) ** 2
        delta = np.zeros(3)
        rotation = self.rotation.copy()
        if case < 3 or case == 4:
            axis = case if case < 3 else 1
            factory = (probe.mink.SO3.from_x_radians, probe.mink.SO3.from_y_radians,
                       probe.mink.SO3.from_z_radians)[axis]
            rotation = self.rotation @ factory(0.35 * wave).as_matrix()
        if case in (3, 4):
            delta = np.array([0.04, -0.03, 0.04]) * wave
        if case == 5:
            delta = np.array([-0.10, 0.20, -0.06]) * wave
        if case >= 6:
            delta, relative_rotation = GetCompositeGoal(case, self.seconds)
            rotation = self.rotation @ relative_rotation
        self.goal = probe.base._matrix_to_se3(rotation, self.origin + delta)
        statuses = []
        for index in range(2):
            previous_q = self.q[index].copy()
            self.config.update(self.q[index])
            if index == 0:
                roll = self.config.get_transform_frame_to_world("right_wrist_roll_link", "body")
                yaw = self.config.get_transform_frame_to_world("right_wrist_yaw_link", "body")
                center = self.goal.translation() - (yaw.translation() - roll.translation())
                target = probe.base._matrix_to_se3(rotation, center)
                plan = self.planner.Plan(self.q[index], target, position_target=center)
                self.q[index] = plan.next_q.copy()
                statuses.append(plan.status)
            else:
                self.wrist.set_target(self.goal)
                velocity = probe.mink.solve_ik(self.config, self.tasks, probe.base.DT,
                    solver=self.planner.solver, damping=probe.base.QP_DAMPING,
                    limits=self.planner.limits, constraints=self.planner.constraints)
                if not self.planner._VelocityValid(velocity, self.planner.right_dofs):
                    self.rejected_steps += 1
                    statuses.append("REJECTED velocity; held previous pose")
                else:
                    self.config.integrate_inplace(velocity, probe.base.DT)
                    self.q[index] = self.config.q.copy()
                    statuses.append("direct QP")
            velocity = np.zeros(self.model.nv)
            probe.mujoco.mj_differentiatePos(self.model, velocity, 1.0, previous_q, self.q[index])
            self.joint_travel[index] += np.abs(np.rad2deg(velocity[self.planner.right_dofs]))
        self.seconds += probe.base.DT
        self.rows = []
        for index in range(2):
            self.config.update(self.q[index])
            actual = self.config.get_transform_frame_to_world("right_wrist_yaw_link", "body")
            self.rows.append({"position_mm": float(np.linalg.norm(actual.translation() - self.goal.translation()) * 1000),
                "rotation_deg": math.degrees(probe.base._rotation_error_radians(rotation, actual.rotation().as_matrix())),
                "clearance_mm": float(self.planner.GetClearance(self.q[index]) * 1000),
                "proximal_travel_deg": float(self.joint_travel[index, :4].sum()),
                "wrist_travel_deg": float(self.joint_travel[index, 4:].sum()),
                "rejected_steps": self.rejected_steps if index == 1 else 0,
                "status": statuses[index]})


def UpdateScene(viewer, simulation, data, selected):
    data.qpos[:] = simulation.q[selected]
    probe.mujoco.mj_forward(simulation.model, data)
    with viewer.lock():
        scene = viewer.user_scn
        scene.ngeom = 1
        probe.mujoco.mjv_initGeom(scene.geoms[0], probe.mujoco.mjtGeom.mjGEOM_SPHERE,
            np.array([0.018] * 3), simulation.goal.translation(), np.eye(3).ravel(),
            np.array([0, 1, 1, 1], dtype=np.float32))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("mink-default", "hardware-guarded"), default="mink-default")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--trajectory-ab", action="store_true", help="Offline standard Mink + stop/through waypoint comparison")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--case", type=int, choices=range(len(CASES)), default=None)
    parser.add_argument("--playback-speed", type=float, default=4,
                        help="Viewer-only playback multiplier; fixed IK timestep is unchanged")
    parser.add_argument("--clip-seconds", type=float, default=20,
                        help="Simulation seconds precomputed per motion")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--viewer-frames", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("frames must be positive")
    if not math.isfinite(args.playback_speed) or not 0.1 <= args.playback_speed <= 16:
        parser.error("playback-speed must be finite and within 0.1..16")
    if not math.isfinite(args.clip_seconds) or not 0 < args.clip_seconds <= 60:
        parser.error("clip-seconds must be finite and within (0, 60]")
    root = Path(__file__).resolve().parents[2]
    output = root / "logs" / "ik_visual_comparison"
    if args.trajectory_ab:
        output = root / "logs" / "experiments" / "trajectory_ab"
    output.mkdir(parents=True, exist_ok=True)
    result = output / "latest.json"
    with tempfile.TemporaryDirectory(prefix="g1_ik_view_") as directory:
        path = probe.base._prepare_mink_xml(output_path=Path(directory) / "model.xml")
        model = probe.mujoco.MjModel.from_xml_path(str(path))
    probe.base._apply_operational_joint_limits(model)
    target_body = model.body("udp_target").id
    model.geom_rgba[model.geom_bodyid == target_body, 3] = 0.0
    if args.trajectory_ab:
        from compare_mink_trajectory import TrajectoryComparison
        simulation = TrajectoryComparison(model, args.profile)
    else:
        simulation = Comparison(model, args.profile)
    labels = ("A stop waypoint", "B through EXPERIMENT") if args.trajectory_ab else ("Hierarchy", "Mink 6D")
    data = probe.mujoco.MjData(model)
    print("OFFLINE ONLY: no VR, UDP, DDS, or robot commands.")
    print("F8: toggle " + " / ".join(labels))
    print("F9: next motion / F10: restart / F12: pause / Close window: exit")
    print("Cyan sphere: requested wrist position. Both solvers share limits and target.")
    print("Result saved to:", result)
    print(f"Recorded playback: {args.playback_speed:g}x; F11 changes speed")
    print("Each motion is calculated once before replay. Fixed dt and limits retained.")
    if args.trajectory_ab:
        print("B is experimental. Case 9: reach 4cm, settle until 20s, turn until 30s, hold.")
    case, selected, paused = (6 if args.case is None else args.case), 0 if args.trajectory_ab else 1, False
    failure = None
    summaries = []
    playback = None
    try:
        if args.headless:
            for case in (range(len(CASES)) if args.case is None else [args.case]):
                simulation.Reset()
                for _ in range(args.frames):
                    simulation.Step(case)
                print(CASES[case], simulation.rows)
                summaries.append({"case": CASES[case], "results": simulation.rows})
            if args.snapshot:
                data.qpos[:] = simulation.q[0]
                probe.mujoco.mj_forward(model, data)
                camera = probe.mujoco.MjvCamera()
                camera.lookat[:] = [0, 0, 1.0]
                camera.distance, camera.azimuth, camera.elevation = 2.2, 135, -15
                model.vis.global_.offwidth, model.vis.global_.offheight = 960, 720
                with probe.mujoco.Renderer(model, height=720, width=960) as renderer:
                    renderer.update_scene(data, camera=camera)
                    from PIL import Image
                    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(renderer.render()).save(args.snapshot)
        else:
            import mujoco.viewer
            events = SimpleQueue()
            with mujoco.viewer.launch_passive(model, data, key_callback=events.put,
                    show_left_ui=False, show_right_ui=False) as viewer:
                viewer.cam.lookat[:] = [0, 0, 1.0]
                viewer.cam.distance, viewer.cam.azimuth, viewer.cam.elevation = 2.2, 135, -15
                viewer_frames = 0
                playback = RecordedPlayback(simulation, args.clip_seconds)

                def progress(done, total):
                    if not viewer.is_running():
                        raise KeyboardInterrupt
                    viewer.set_texts([(probe.mujoco.mjtFontScale.mjFONTSCALE_150,
                        probe.mujoco.mjtGridPos.mjGRID_TOPLEFT,
                        f"Calculating {CASES[case]}: {done}/{total}", "")])
                    viewer.sync()

                data.qpos[:] = simulation.initial
                probe.mujoco.mj_forward(model, data)
                playback.Prepare(case, progress)
                # Do not replay keys entered while the first clip was calculating.
                while not events.empty():
                    events.get()
                previous = time.monotonic()
                while viewer.is_running():
                    started = time.monotonic()
                    playback.Advance(started - previous, args.playback_speed, paused)
                    previous = started
                    while not events.empty():
                        key = events.get()
                        if key == glfw.KEY_F11:
                            args.playback_speed = NextPlaybackSpeed(args.playback_speed)
                            continue
                        old_case = case
                        case, selected, paused = HandleComparisonKey(
                            key, playback, case, selected, paused)
                        if case != old_case:
                            playback.Prepare(case, progress)
                            while not events.empty():
                                events.get()
                            previous = time.monotonic()
                    UpdateScene(viewer, playback, data, selected)
                    lines = [f"{name}: pos {r['position_mm']:.1f} mm / rot {r['rotation_deg']:.1f} deg / gap {r['clearance_mm']:.1f} mm\n"
                             f"  travel: arm {r['proximal_travel_deg']:.1f} deg / wrist {r['wrist_travel_deg']:.1f} deg\n"
                             f"  {r['status']} | rejected {r['rejected_steps']}"
                             for i, (name, r) in enumerate(zip(labels, playback.rows))]
                    if args.trajectory_ab and case == 9:
                        lines += [f"{name} rotation-only arm travel [SP/SR/SY/E]: "
                                  + "/".join(f"{v:.1f}" for v in r['rotation_phase_arm_travel_deg'])
                                  + f" deg | settled before turn: {r['rotation_start_settled']}"
                                  for name, r in zip(labels, playback.rows)]
                    viewer.set_texts([(probe.mujoco.mjtFontScale.mjFONTSCALE_150,
                        probe.mujoco.mjtGridPos.mjGRID_TOPLEFT,
                        f"REPLAY | {args.playback_speed:g}x | {labels[selected]} | {CASES[case]} | {playback.seconds:.1f}s\n"
                        + "\n".join(lines) + "\n" + CONTROL_HELP, "")])
                    viewer.sync()
                    viewer_frames += 1
                    if args.viewer_frames and viewer_frames >= args.viewer_frames:
                        break
                    time.sleep(max(0.0, probe.base.DT - (time.monotonic() - started)))
    except Exception as error:
        failure = repr(error)
        raise
    finally:
        result.write_text(json.dumps({"robot_command": False, "profile": args.profile,
            "comparison_labels": labels,
            "trajectory_ab": args.trajectory_ab,
            "viewer_playback_speed": args.playback_speed,
            "motion_cycle_s": 20.0,
            "case": CASES[case], "simulation_time_s": (playback or simulation).seconds,
            "results": (playback or simulation).rows, "error": failure,
            "headless_cases": summaries,
            "boundary": ("Offline synthetic A/B trajectory experiment, not a validated improvement or hardware test."
                         if args.trajectory_ab else "Kinematic visual comparison only. Standard QP uses project G1 costs and constraints, not unmodified upstream demo. Hierarchy includes additional planner acceptance. No physical validation.")},
            indent=2, allow_nan=False), encoding="utf-8")
        print("Result saved to:", result)


if __name__ == "__main__":
    main()
