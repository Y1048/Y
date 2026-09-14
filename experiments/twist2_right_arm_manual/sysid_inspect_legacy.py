"""Read-only inventory of v1 recordings; never converts missing v2 fields."""
import argparse
import json
from pathlib import Path
from real_response_log import parse_trace, JOINT_INDICES, JOINT_NAMES


def inspect(path):
    trace=parse_trace(path)
    r=trace.records
    clocks=[x['lowstate_monotonic_ns'] for x in r]
    writes=[x['command_monotonic_ns'] for x in r]
    ranges=[max(x['command_q_rad'][j] for x in r)-min(x['command_q_rad'][j] for x in r)
            for j in range(7)]
    repeated=sum(a==b for a,b in zip(clocks,clocks[1:]))
    conflicting=sum(a['lowstate_monotonic_ns']==b['lowstate_monotonic_ns'] and
                    any(a[k]!=b[k] for k in ('measured_q_rad','measured_dq_rad_s'))
                    for a,b in zip(r,r[1:]))
    blockers=['legacy7_axis_schema_not_v2', 'write_begin_not_proven',
              'no_v2_complete_capture_receipt', 'no_independent_validation_episode']
    if trace.dropped_sequences: blockers.append('sequence_gaps')
    if conflicting: blockers.append('conflicting_repeated_state')
    if not any(x>1e-6 for x in ranges): blockers.append('no_command_excitation')
    if any(a!=b for a,b in zip(clocks,writes)): blockers.append('asynchronous_timestamps')
    return dict(schema='g1.sysid.legacy-readiness.v1',source=str(path),sha256=trace.sha256,
                records=len(r),recorded_joints=list(JOINT_INDICES),joint_names=list(JOINT_NAMES),
                command_excursion_rad=ranges,sequence_gaps=trace.dropped_sequences,
                repeated_state_records=repeated,conflicting_state_records=conflicting,
                duration_s=(writes[-1]-writes[0])*1e-9,fit_ready=False,blockers=blockers,
                recommended_hardware_gains=None,
                note='Excursion is data screening, not physical identifiability; no measurement or conversion performed.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('trace');p.add_argument('--output',required=True)
    args=p.parse_args();report=inspect(args.trace)
    with Path(args.output).open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
