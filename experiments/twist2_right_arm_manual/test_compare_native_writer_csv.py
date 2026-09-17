import csv
from compare_native_writer_csv import Compare


def test_old_csv_is_not_reconstructed(tmp_path):
    path=tmp_path/'old.csv';path.write_text('desired_target_0,q_0\n1,0\n')
    assert Compare(path)['status']=='insufficient_evidence'


def test_uses_paired_writer_state_and_skips_rejected_duplicate_attempts(tmp_path):
    row=dict(writer_attempt_sequence=1,writer_sdk_accepted=1,writer_damping=0,
             desired_target_0=999,q_0=999)
    for i in range(29):
        for key,value in zip(('desired','target','q','dq','kp','kd','ff'),(1,.5,.25,.1,10,2,1)):
            row[f'writer_{key}_{i}']=value
    rejected=dict(row,writer_attempt_sequence=2,writer_sdk_accepted=0)
    damping=dict(row,writer_attempt_sequence=3,writer_damping=1)
    path=tmp_path/'new.csv'
    with path.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=row.keys());writer.writeheader()
        writer.writerows([row,row,rejected,damping])
    result=Compare(path)
    assert result['unique_attempts']==3 and result['rejected_attempts']==1
    assert result['damping_attempts']==1
    joint=result['joints'][0]
    assert joint['sampled_active_attempts']==1
    assert joint['maximum_limiter_delta']==.5
    assert joint['maximum_policy_state_error']==.75
    assert joint['maximum_command_state_error']==.25
    assert abs(joint['maximum_predicted_pd_torque']-3.3)<1e-12
