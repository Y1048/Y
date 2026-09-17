"""Wall-clock local pipe test; synthetic fixed/lag state, no robot IO or G1 dynamics."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import time
from pathlib import Path
from run_owner_cpu_offline import Owner,ROOT
from policy_worker_client_offline import PolicyWorkerClient

def Main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--startup-blend',action='store_true')
    p.add_argument('--dispatch',action='store_true',help='Use memory-only dispatch with a 6 ms gap limit')
    p.add_argument('--autonomous-tick',action='store_true',help='C++ thread supplies synthetic state and memory dispatch')
    p.add_argument('--tracking-fixture',action='store_true',help='Synthetic lag response, startup then arm motion and release')
    p.add_argument('--torque-fade',action='store_true',help='Tracking fixture with synthetic +/-0.5 Nm startup torque')
    args=p.parse_args()
    if args.torque_fade:args.tracking_fixture=True
    if args.tracking_fixture:args.autonomous_tick=True;args.startup_blend=True
    if args.autonomous_tick:args.dispatch=True
    capture=ROOT/'logs/test_results/twist2_vr_shadow_20260907_175950_1b96b661/samples.jsonl'
    for line in capture.read_text().splitlines():
        r=json.loads(line)
        if r.get('payload_base64'):
            packet=json.loads(base64.b64decode(r['payload_base64']))
            if packet.get('input_command_mode')=='active':break
    python=ROOT/'logs/diagnostics/twist2_cpu_venv/Scripts/python.exe'
    worker=PolicyWorkerClient([str(python),'-B',str(ROOT/'experiments/twist2_right_arm_manual/policy_cpu_worker_offline.py')])
    owner=Owner();events=[];cycles=[];error=None
    count=1200 if args.tracking_fixture else (600 if args.startup_blend else 100)
    release_verified=False
    right_target_delta=None;right_measured_delta=None;other_upper_delta=None
    def Call(**kw):
        reply=owner.call(**kw)
        events.append(dict(op=kw['op'],time=reply['event_time'],reason=reply['reason'],commits=reply['commits'],phase=reply['phase'],
            dispatch_count=reply['dispatch_count'],dispatch_time=reply['dispatch_time'],
            dispatch_state=reply['dispatch_state'],handoff_required=reply['handoff_required'],
            background_ticks=reply['background_ticks'],background_gap_ms_max=reply['background_gap_ms_max'],
            owner_lock_wait_ms_max=reply['owner_lock_wait_ms_max'],
            dispatch_gap_ms_min=reply['dispatch_gap_ms_min'],dispatch_gap_ms_max=reply['dispatch_gap_ms_max']))
        if args.tracking_fixture:
            events[-1].update(measured_q=reply['measured_q'],desired=reply['desired'],active_steps=reply['active_steps'])
        if args.torque_fade:events[-1]['writer_feedforward']=reply['writer_feedforward']
        return reply
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending=Call(op='init',packet=packet,wall_clock=True,startup_blend=args.startup_blend,dispatch=args.dispatch,
                autonomous_tick=args.autonomous_tick,tracking_fixture=args.tracking_fixture,torque_fade=args.torque_fade)
            initial_q=pending['measured_q']
            writer_seen=False
            last_tick=time.perf_counter();started=last_tick
            for cycle in range(count):
                if pending['reason']:break
                t0=time.perf_counter()
                future=pool.submit(worker.infer,pending['observation'])
                while not future.done():
                    if not args.autonomous_tick and time.perf_counter()-last_tick>=.002:
                        state=Call(op='state');tick=Call(op='tick');last_tick=time.perf_counter()
                        if state['reason'] or tick['reason']:break
                    time.sleep(.0002)
                reply=future.result(timeout=5)
                finish=Call(op='finish',token=pending['token'],action=reply['action'])
                cycles.append(dict(index=cycle,accepted=finish.get('accepted'),commits=finish['commits'],
                    owner_request_to_finish_ms=(finish['event_time']-pending['event_time'])*1000,
                    phase=finish['phase'],
                    worker_total_ms=reply.get('total_ms'),worker_model_ms=reply.get('model_ms'),
                    worker_gc_events=reply.get('gc_events'),
                    python_infer_and_events_ms=(time.perf_counter()-t0)*1000,reason=finish['reason']))
                if finish['reason']:break
                if args.tracking_fixture and finish['phase']=='active' and finish['active_steps']>=20:
                    right_target_delta=finish['desired'][22]-initial_q[22]
                    right_measured_delta=finish['measured_q'][22]-initial_q[22]
                    other_upper_delta=max(abs(finish['desired'][i]-initial_q[i])
                        for i in list(range(12,22))+list(range(23,29)))
                    released=Call(op='release')
                    time.sleep(.03)
                    held=Call(op='status')
                    release_verified=(released['reason']=='input_disengaged' and held['handoff_required']
                        and held['dispatch_count']==released['dispatch_count']
                        and held['commits']==released['commits'] and held['desired'] is None
                        and .005<right_target_delta<=.020001 and right_measured_delta>0
                        and other_upper_delta==0)
                    if not release_verified:raise AssertionError('release did not latch')
                    break
                if finish['writer_present'] and not writer_seen:
                    last_tick=time.perf_counter();writer_seen=True
                while time.perf_counter()-t0<.01:
                    if not args.autonomous_tick and time.perf_counter()-last_tick>=.002:
                        Call(op='state');tick=Call(op='tick');last_tick=time.perf_counter()
                        if tick['reason']:break
                    time.sleep(.0002)
                pending=Call(op='begin') if cycle<count-1 else finish
            if args.autonomous_tick:Call(op='status')
            final_reason=events[-1]['reason']
            elapsed=time.perf_counter()-started
            if final_reason and args.dispatch:
                frozen_count=events[-1]['dispatch_count']
                for _ in range(2):
                    probe=Call(op='status' if args.autonomous_tick else 'tick')
                    if probe['dispatch_count']!=frozen_count or not probe['handoff_required']:
                        raise AssertionError('dispatch stop did not latch')
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}';elapsed=None;final_reason='runner_error'
    finally:
        owner.close();worker.close()
    previous_count=events[-1]['dispatch_count'] if events else 0
    ticks=[event['time'] for event in events if event['op']=='tick']
    tick_gaps=[(b-a)*1000 for a,b in zip(ticks,ticks[1:])]
    result=dict(offline_only=True,synthetic_fixed_state=not args.tracking_fixture,
        synthetic_lag_fixture=args.tracking_fixture,release_verified=release_verified,robot_output=False,requested_cycles=count,
        torque_fade=args.torque_fade,
        right_target_delta=right_target_delta,right_measured_delta=right_measured_delta,other_upper_delta=other_upper_delta,
        dispatch_enabled=args.dispatch,dispatch_count=previous_count,
        autonomous_tick=args.autonomous_tick,
        background_ticks=events[-1]['background_ticks'] if events else 0,
        background_gap_ms_max=events[-1]['background_gap_ms_max'] if events else None,
        owner_lock_wait_ms_max=events[-1]['owner_lock_wait_ms_max'] if events else None,
        dispatch_gap_ms_min=events[-1]['dispatch_gap_ms_min'] if events else None,
        dispatch_gap_ms_max=events[-1]['dispatch_gap_ms_max'] if events else None,
        tick_call_gap_ms_max=max(tick_gaps,default=None),
        startup_blend=args.startup_blend,phases=sorted(set(e['phase'] for e in events)),
        accepted_cycles=sum(bool(c['accepted']) for c in cycles),elapsed_s=elapsed,
        final_reason=final_reason,error=error,cycles=cycles,events=events,
        note='C++ steady_clock timestamps include observation delivery, Python scheduling and policy IPC before Finish dispatch; no hard real-time guarantee.')
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('cycles','events')},indent=2))
    if args.tracking_fixture:
        if not release_verified or error:raise SystemExit(1)
    elif result['accepted_cycles']!=count or final_reason or error or (args.startup_blend and 'active' not in result['phases']):raise SystemExit(1)

if __name__=='__main__':Main()
