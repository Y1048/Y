"""Display-only geometric bilateral IK goal; never a motor target.

A private joint/collision constrained solve separates reachable goal geometry
from the live controller's velocity/acceleration-limited progress. The live
loop never waits or consumes this result. This is a local feasible witness,
not a global workspace solution or proof of physical arrival.
"""
from contextlib import contextmanager
import hashlib
import json
from dataclasses import asdict, is_dataclass
import io
import os
import pickle
import signal
import time
from concurrent.futures import ProcessPoolExecutor

import mink
import mujoco
import numpy as np
from g1_bimanual_target import BASIS

SCHEMA = 'g1.bimanual.goal.preview.v2'
MAXIMUM_ITERATIONS = 64
SOLVE_BUDGET_S = .04
UPDATE_PERIOD_S = 1.0 / 60.0
# Submit at the control cadence only when the single worker is free. Actual
# result rate depends on computation; do not queue stale snapshots or wait.
# Never extend the display lifetime by retransmitting a frame.
MAXIMUM_AGE_S = .20
_WORKER_NATIVE = None
_WORKER_GEOMETRIC_CACHE = None


@contextmanager
def _child_math_environment():
    # The live process already imported its numeric libraries. Only the spawned
    # display process reads these startup settings; restore the parent process
    # environment immediately after ProcessPoolExecutor.submit starts the child.
    names = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')
    previous = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ[name] = '1'
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _native_objects(source):
    return dict(model=source.model, configuration=source.config.data,
                check=source.check_data, target=source.checked_target_data,
                left=source.motion['left'].distance_probe_data,
                right=source.motion['right'].distance_probe_data)


def _snapshot_objects(source):
    # These caches are constructed once in the canonical controller. Reuse the
    # worker's private equivalents rather than reserializing geometry tables
    # every frame. Limits contain private scratch arrays, overwritten per call.
    # Dynamic q, velocity, stopping tails and arm-policy state are still copied.
    objects = _native_objects(source)
    for name in ('names', 'qids', 'dofs', 'pairs', 'policy_pairs', 'caps',
                 'return_caps', 'profile', 'return_profile', 'limits',
                 'pair_array', 'ranges', '_clearance_local_centers',
                 '_clearance_bounding_radii'):
        objects['cache:' + name] = getattr(source, name)
    return objects


def _contract_digest(source):
    # Check configuration, not object identities or uninitialized solver scratch.
    # Stable canonical values also avoid pickle memo/alias differences across spawn.
    scratch = {'model', '_phi', '_ball_G', '_ball_h',
               '_fromto', '_normal', '_jac1', '_jac2'}
    def canonical(value):
        if isinstance(value, np.ndarray):
            return dict(dtype=value.dtype.str, shape=value.shape,
                        values=value.tolist())
        if is_dataclass(value):
            return canonical(asdict(value))
        if isinstance(value, dict):
            return {str(k): canonical(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [canonical(v) for v in value]
        if isinstance(value, np.generic):
            return value.item()
        return value
    constants = {k: v for k, v in _snapshot_objects(source).items()
                 if k.startswith('cache:') and k != 'cache:limits'}
    constants['cache:limits'] = [
        {k: v for k, v in vars(limit).items() if k not in scratch}
        for limit in source.limits]
    digest = hashlib.sha256(_model_digest(source.model).encode())
    digest.update(json.dumps(canonical(constants), sort_keys=True,
                             separators=(',', ':')).encode())
    return digest.hexdigest()


def _model_digest(model):
    digest = hashlib.sha256(bytes(model.names))
    for name in ('jnt_type', 'jnt_qposadr', 'jnt_dofadr', 'jnt_range',
                 'body_parentid', 'body_pos', 'body_quat', 'geom_type',
                 'geom_bodyid', 'geom_size', 'geom_pos', 'geom_quat',
                 'mesh_vert', 'mesh_face'):
        digest.update(np.asarray(getattr(model, name)).tobytes())
    return digest.hexdigest()


class _SnapshotWriter(pickle.Pickler):
    def __init__(self, stream, tokens):
        super().__init__(stream, protocol=5)
        self.tokens = tokens

    def persistent_id(self, obj):
        token = self.tokens.get(id(obj))
        if token is not None:
            return token
        if isinstance(obj, (mujoco.MjModel, mujoco.MjData)):
            raise ValueError('Unregistered native object in preview snapshot')
        return None


class _SnapshotReader(pickle.Unpickler):
    def persistent_load(self, token):
        return _WORKER_NATIVE[token]


def _initialize_worker():
    global _WORKER_NATIVE, _WORKER_GEOMETRIC_CACHE
    _WORKER_GEOMETRIC_CACHE = None
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.SetPriorityClass.restype = wintypes.BOOL
        # IDLE_PRIORITY_CLASS applies only to this owned display process. It
        # must yield CPU to the normal-priority IK and operator application.
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x40):
            raise OSError('Cannot lower display-preview process priority')
        # Pin the single numerical worker to one allowed logical processor to
        # reduce migration and preferred-core contention. Parent unchanged.
        kernel.GetProcessAffinityMask.argtypes = (
            wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t))
        kernel.GetProcessAffinityMask.restype = wintypes.BOOL
        kernel.SetProcessAffinityMask.argtypes = (wintypes.HANDLE, ctypes.c_size_t)
        kernel.SetProcessAffinityMask.restype = wintypes.BOOL
        allowed = ctypes.c_size_t()
        system = ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(),
                                            ctypes.byref(allowed), ctypes.byref(system)):
            raise OSError('Cannot inspect display-preview process affinity')
        if allowed.value.bit_count() > 1:
            one_cpu = 1 << (allowed.value.bit_length() - 1)
            if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), one_cpu):
                raise OSError('Cannot isolate display-preview process affinity')
    else:
        os.nice(5)
    from g1_bimanual_sim import BimanualSimulation
    worker = BimanualSimulation()
    _WORKER_NATIVE = _snapshot_objects(worker)
    _WORKER_NATIVE['contract'] = _contract_digest(worker)


def _worker_ready():
    return _WORKER_NATIVE['contract']


def _wrist_poses(sim):
    return {side: sim.config.get_transform_frame_to_world(
        side + '_wrist_yaw_link', 'body') for side in ('left', 'right')}


def _prefer_recovery(candidate, incumbent):
    """Do not buy one arm's position improvement with the other arm's error.

    Position comparisons use the solver's one-millimetre spatial tolerance;
    at least two millimetres of improvement are required to change branches.
    Orientation
    breaks ties only when both candidates already satisfy position tolerance.
    This ranks local witnesses; it does not establish global reachability.
    """
    if not candidate['valid']:
        return False
    if not incumbent['valid']:
        return True
    sides = ('left', 'right')
    new = np.array([candidate['position_error_m'][s] for s in sides])
    old = np.array([incumbent['position_error_m'][s] for s in sides])
    # A 0.02 mm trade in one arm must not veto an 85 mm improvement of the
    # other. These are position-ranking tolerances, NOT relaxed joint limits,
    # clearance, or acceptance of an unchecked witness. Net progress and a
    # larger switching threshold prevent equivalent branches from chattering.
    gain = old - new
    if (np.all(new <= old + .001 + 1e-9) and np.max(gain) >= .002
            and np.sum(gain) > .001):
        return True
    if max(np.max(new), np.max(old)) <= .001:
        new_rotation = np.array([candidate['orientation_error_rad'][s] for s in sides])
        old_rotation = np.array([incumbent['orientation_error_rad'][s] for s in sides])
        return bool(np.all(new_rotation <= old_rotation + 1e-9)
                    and np.max(old_rotation - new_rotation) >= np.deg2rad(1.))
    return False


def _solve_with_recovery(sim, goals, q, cache, *, deadline=None):
    """Two private branches share one deadline and at most 64 iterations.

    A checked but inaccurate warm solution is not the only starting point.
    An independent reference/live branch can progress across fresh requests;
    it need not reach the better basin within one display calculation. All
    candidates are evaluated against this request, never cached old errors.
    Only arm coordinates are cached. Neither branch is a command trajectory.
    """
    from g1_bimanual_geometric_goal import solve_geometric_goal

    def seed(arm_q):
        if arm_q is None:
            return None
        value = q.copy()
        value[sim.qids] = arm_q
        return value

    def remaining():
        return None if deadline is None else max(0., deadline - time.perf_counter())

    def solve(initial, iterations, duration):
        sim.config.update(q)
        return solve_geometric_goal(sim, goals, initial_q=initial,
                                    max_iterations=iterations, max_duration_s=duration)

    cache = {} if cache is None else cache
    primary_seed = seed(cache.get('arm_q'))
    primary_kind = cache.get('seed_kind', 'live')
    if primary_seed is not None and np.isfinite(primary_seed).all():
        # The current command can be a better checked starting point after a
        # large change of hand goal. Compare FK against *today's* goal before
        # spending the iteration budget on a now-inappropriate cached branch.
        from g1_bimanual_geometric_goal import _errors, _poses
        sim.config.update(q)
        live_position, live_rotation = _errors(_poses(sim), goals)
        sim.config.update(primary_seed)
        warm_position, warm_rotation = _errors(_poses(sim), goals)
        live = dict(valid=True, position_error_m=live_position, orientation_error_rad=live_rotation)
        warm = dict(valid=True, position_error_m=warm_position, orientation_error_rad=warm_rotation)
        if _prefer_recovery(live, warm):
            primary_seed = None
            primary_kind = 'live'
        sim.config.update(q)
    duration = remaining()
    if duration == 0.:
        # Hide this expired calculation, but do not erase earlier checked
        # search progress just because the OS delayed this job. The next fresh
        # request still revalidates both seeds against its current body/goal.
        return dict(valid=False, status='time_budget'), cache or None
    # Reserve half the remaining time for an independent branch. A single
    # native call is non-preemptible; this is still a cooperative deadline.
    primary = solve(primary_seed, 48, None if duration is None else duration / 2.)
    primary['seed_kind'] = primary_kind
    primary['recovery_attempted'] = False
    primary['recovery_selected'] = False
    selected = primary
    recovery = None
    recovery_seed = cache.get('recovery_seed', 'reference')
    recovery_arm = cache.get('recovery_arm_q')
    needs_recovery = (not primary['valid']
                      or max(primary['position_error_m'].values()) > .005)
    duration = remaining()
    if needs_recovery and duration != 0.:
        if recovery_arm is None:
            if recovery_seed == 'reference':
                reference = q.copy()
                for side in ('left', 'right'):
                    policy = sim.motion[side]
                    reference[policy.qpos_ids] = policy.posture_reference[policy.qpos_ids]
                recovery_arm = reference[sim.qids].copy()
            else:
                recovery_arm = q[sim.qids].copy()
        recovery = solve(seed(recovery_arm), 16, duration)
        if _prefer_recovery(recovery, primary):
            selected = recovery
            selected['seed_kind'] = recovery_seed
            selected['recovery_selected'] = True
        selected['recovery_attempted'] = True
        # Keep promising unfinished work, including a native-call budget
        # expiry before its first accepted step. Restart stationary/invalid
        # alternatives on the other known seed, not the same dead branch.
        if (recovery['valid'] and selected is primary
                and (recovery['iterations'] > 0 or recovery['termination'] == 'time_budget')):
            recovery_arm = recovery['q'][sim.qids].copy()
        else:
            recovery_arm = None
            recovery_seed = 'live' if recovery_seed == 'reference' else 'reference'
    if not selected['valid']:
        sim.config.update(q)
        return selected, None
    selected.setdefault('recovery_selected', False)
    sim.config.update(selected['q'])
    return selected, dict(arm_q=selected['q'][sim.qids].copy(),
                          seed_kind=selected['seed_kind'],
                          recovery_arm_q=recovery_arm, recovery_seed=recovery_seed)


def _rollout(payload, q, goals, generation, context, source_time, sequence):
    global _WORKER_GEOMETRIC_CACHE
    started = time.perf_counter()
    sim = _SnapshotReader(io.BytesIO(payload)).load()
    q = np.asarray(q, dtype=float)
    invalid_q = (q.shape != (sim.model.nq,) or not np.isfinite(q).all())
    if not invalid_q:
        invalid_q = bool(np.any(q[sim.qids] < sim.ranges[:, 0] - 1e-9)
                         or np.any(q[sim.qids] > sim.ranges[:, 1] + 1e-9))
    if invalid_q:
        return dict(valid=False, generation=generation, context=context,
                    source_time=source_time, status='invalid_start')
    sim.config.update(q)
    clearance = sim.clearance(q)
    if not np.isfinite(clearance) or clearance < sim.clearance_m:
        return dict(valid=False, generation=generation, context=context,
                    source_time=source_time, status='invalid_start')
    cache_key = (generation, context)
    cache = None
    if (_WORKER_GEOMETRIC_CACHE is not None
            and _WORKER_GEOMETRIC_CACHE['key'] == cache_key):
        cache = _WORKER_GEOMETRIC_CACHE
    deadline = None if SOLVE_BUDGET_S is None else started + SOLVE_BUDGET_S
    solution, updated = _solve_with_recovery(sim, goals, q, cache, deadline=deadline)
    _WORKER_GEOMETRIC_CACHE = None if updated is None else dict(updated, key=cache_key)
    if not solution['valid']:
        return dict(valid=False, generation=generation, context=context,
                    source_time=source_time, status=solution['status'])
    rotation = sim.base_rotation.T
    body_poses = {side: (rotation @ pose.translation(),
                        rotation @ pose.rotation().as_matrix())
                  for side, pose in solution['poses'].items()}
    return dict(valid=True, generation=generation, context=context,
                source_time=source_time, sequence=sequence,
                poses=body_poses, iterations=solution['iterations'],
                status=solution['status'],
                termination=solution['termination'],
                seed_kind=solution['seed_kind'],
                recovery_attempted=solution['recovery_attempted'],
                recovery_selected=solution['recovery_selected'],
                position_error_m=[solution['position_error_m'][s] for s in ('left', 'right')],
                orientation_error_rad=[solution['orientation_error_rad'][s] for s in ('left', 'right')],
                minimum_clearance_m=solution['minimum_clearance_m'],
                compute_ms=(time.perf_counter() - started) * 1000)



class BimanualGoalPreview:
    """One owned low-priority process, one in-flight job, no queued backlog.

    Construct before the input listener starts. Polling never waits; failure,
    stale results and session changes invalidate only the display prediction.
    The process has no control socket, actuator connection or command publisher.
    """
    @staticmethod
    def metadata():
        return dict(schema=SCHEMA, display_only=True, geometric_goal=True, maximum_iterations=MAXIMUM_ITERATIONS,
                    solve_budget_s=SOLVE_BUDGET_S,
                    recovery='persistent_reference_live_branch',
                    recovery_position_threshold_m=.005,
                    recovery_position_comparison_tolerance_m=.001,
                    recovery_minimum_improvement_m=.002,
                    update_hz=1. / UPDATE_PERIOD_S, maximum_source_age_s=MAXIMUM_AGE_S,
                    command_generation_unchanged=True)

    def __init__(self, source):
        self.tokens = {id(value): key for key, value in _snapshot_objects(source).items()}
        self.executor = None
        self.pending = None
        self.result = None
        self.context = None
        self.generation = 0
        self.next_submit = 0.
        self.error = None
        self.closed = False
        self.last_snapshot_ms = 0.
        self.initializing = None
        self.worker_ready = False
        self.started = time.perf_counter()
        self.model_digest = _contract_digest(source)
        try:
            with _child_math_environment():
                self.executor = ProcessPoolExecutor(
                    max_workers=1, initializer=_initialize_worker)
                self.initializing = self.executor.submit(_worker_ready)
        except Exception as error:
            self._disable(error)

    def _disable(self, error):
        self.error = type(error).__name__ + ': ' + str(error)[:160]
        self.result = None
        print('[GOAL PREVIEW] disabled; control unchanged: ' + self.error, flush=True)

    def feedback(self, context, now, base_rotation):
        if self.initializing is not None and self.initializing.done():
            try:
                if self.initializing.result() != self.model_digest:
                    raise ValueError('Display preview model differs from live model')
                self.worker_ready = True
            except Exception as error:
                self._disable(error)
            self.initializing = None
        elif self.initializing is not None and now - self.started > 15 and not self.error:
            self._disable(TimeoutError('Display preview initialization timed out'))
        if context != self.context:
            self.context = context
            self.generation += 1
            self.result = None
            self.next_submit = 0.
        if self.pending is not None and self.pending.done():
            try:
                candidate = self.pending.result()
                if (candidate['generation'] == self.generation
                        and candidate['context'] == context):
                    self.result = candidate
            except Exception as error:
                self._disable(error)
            self.pending = None
        result = self.result
        invalid = dict(schema=SCHEMA, valid=False,
                       status='disabled' if self.error or self.closed else 'waiting')
        if (self.closed or self.error or context is None or result is None
                or not isinstance(result, dict) or not result.get('valid', False)
                or not np.isfinite(now)):
            return invalid
        try:
            age = now - result['source_time']
            if not np.isfinite(age) or not 0 <= age <= MAXIMUM_AGE_S:
                invalid['status'] = 'stale'
                return invalid
            if (type(result['iterations']) is not int
                    or not 0 <= result['iterations'] <= MAXIMUM_ITERATIONS
                    or result['status'] not in ('geometric_goal_converged', 'geometric_goal_partial')
                    or type(result['sequence']) is not int
                    or not 0 <= result['sequence'] <= 9007199254740991
                    or not np.isfinite(result['compute_ms']) or result['compute_ms'] < 0
                    or not np.isfinite(result['minimum_clearance_m'])
                    or result['minimum_clearance_m'] < .005 - 1e-9):
                raise ValueError('Invalid geometric-goal worker result')
            for key in ('position_error_m', 'orientation_error_rad'):
                values = np.asarray(result[key], dtype=float)
                if values.shape != (2,) or not np.isfinite(values).all() or np.any(values < 0):
                    raise ValueError('Invalid geometric-goal residual')
            output = dict(schema=SCHEMA, valid=True, status=result['status'],
                          age_s=age, iterations=result['iterations'],
                          minimum_clearance_m=result['minimum_clearance_m'],
                          position_error_m=list(result['position_error_m']),
                          orientation_error_rad=list(result['orientation_error_rad']),
                          source_sequence=result['sequence'], compute_ms=result['compute_ms'])
            # Add diagnostic provenance without changing the v2 pose contract.
            # Older recordings can omit these fields. Unity ignores additions.
            for key in ('termination', 'seed_kind', 'recovery_attempted', 'recovery_selected'):
                if key in result:
                    output[key] = result[key]
            for side in ('left', 'right'):
                position, rotation = result['poses'][side]
                position = np.asarray(position)
                rotation = np.asarray(rotation)
                if (position.shape != (3,) or rotation.shape != (3, 3)
                        or not np.isfinite(position).all() or not np.isfinite(rotation).all()
                        or not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-6, rtol=0)
                        or abs(np.linalg.det(rotation) - 1) > 1e-6):
                    raise ValueError('Invalid goal-preview pose')
                output[side + '_world_m'] = (
                    BASIS.T @ base_rotation @ position).tolist()
                output[side + '_world_wxyz'] = mink.SO3.from_matrix(
                    BASIS.T @ base_rotation @ rotation @ BASIS).wxyz.tolist()
            # Validate serialization here so display errors cannot break the
            # main feedback/log writer after the command has been published.
            json.dumps(output, allow_nan=False)
            return output
        except (KeyError, TypeError, ValueError) as error:
            self._disable(error)
            invalid['status'] = 'disabled'
            return invalid

    def request(self, source, goals, now, sequence):
        if (self.closed or self.error or not self.worker_ready or self.context is None
                or self.pending is not None or now < self.next_submit):
            return False
        try:
            started = time.perf_counter()
            stream = io.BytesIO()
            _SnapshotWriter(stream, self.tokens).dump(source)
            payload = stream.getvalue()
            q = source.config.q.copy()
            self.last_snapshot_ms = (time.perf_counter() - started) * 1000
            self.pending = self.executor.submit(
                _rollout, payload, q, goals, self.generation, self.context,
                now, sequence)
            self.next_submit = now + UPDATE_PERIOD_S
            return True
        except Exception as error:
            self._disable(error)
            return False

    def close(self):
        self.closed = True
        self.result = None
        if self.executor is not None:
            self.executor.shutdown(wait=True, cancel_futures=True)
