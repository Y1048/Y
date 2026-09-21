"""Read existing bimanual/Omni logs and print latest values; no network or actuation.

50 Hz is the display target, not the source update rate or a UDP resend rate.
Each stream's sequence and age distinguish new data from repeated snapshots.
"""
import argparse
import csv
import io
import json
import math
from pathlib import Path
import time

SUFFIXES = ('shoulder_pitch', 'shoulder_roll', 'shoulder_yaw', 'elbow',
            'wrist_roll', 'wrist_pitch', 'wrist_yaw')
JOINTS = [side+'_'+name+'_joint' for side in ('left', 'right') for name in SUFFIXES]


def finite(values, count):
    return isinstance(values, list) and len(values)==count and all(
        type(x) in (int, float) and math.isfinite(x) for x in values)


def arm_value(row):
    if row.get('kind') != 'state':
        return None
    if (row.get('schema') != 'g1.bimanual.unity.sim.state.v1'
            or row.get('simulation_only') is not True or row.get('joint_names') != JOINTS
            or not finite(row.get('q_rad'), 14)):
        raise ValueError('invalid bimanual schema/order/q')
    stamp = row.get('monotonic_s')
    if type(stamp) not in (int, float) or not math.isfinite(stamp):
        raise ValueError('invalid arm timestamp')
    return dict(source_monotonic_s=stamp, sequence=row.get('sequence'),
                feedback_sequence=row.get('feedback_sequence'), session=row.get('session'),
                state=row.get('state'), reason=row.get('reason'),
                left_q_rad=row['q_rad'][:7], right_q_rad=row['q_rad'][7:])


def omni_value(row):
    if row.get('schema') != 'g1.omni.timeseries.v1':
        raise ValueError('invalid Omni CSV schema')
    names = ('receive_monotonic_s','mx','my','arm_yaw_deg','omni_yaw_rate_deg_s',
             'vx','vy','yaw_rate','yaw_diff_deg','yaw_step_diff_deg')
    values = {name:float(row[name]) for name in names}
    if not all(math.isfinite(x) for x in values.values()):
        raise ValueError('nonfinite Omni sample')
    return dict(source_monotonic_s=values.pop('receive_monotonic_s'),
                sample_sequence=int(row['sample_sequence']), calibrated=row['calibrated']=='1',
                **values)


class LogTail:
    """Follow new records, retaining historical values with an explicit label."""
    def __init__(self, mode):
        self.mode=mode
        self.path=None
        self.handle=None
        self.pending=b''
        self.header=None
        self.value=None
        self.error=None
        self.updated=None
        self.revision=0

    def select(self, path):
        if path==self.path:
            return
        if self.handle:
            self.handle.close()
        self.path=path
        self.handle=None
        self.pending=b''
        self.header=None
        self.value=None
        self.error=None
        self.updated=None
        if path is None:
            return
        self.handle=path.open('rb')
        if self.mode=='omni':
            self.header=next(csv.reader([self.handle.readline().decode('utf-8-sig')]))
        # Initial history is displayed as historical, never fresh receipt.
        # Seek near EOF for large JSONL. CSV must retain quoted record boundaries.
        if self.mode=='arm' and path.stat().st_size>1048576:
            self.handle.seek(-1048576,2)
            self.handle.readline()
        while self.poll(time.monotonic(), initial=True):
            pass

    def poll(self, now, initial=False):
        if self.handle is None:
            return False
        if self.path.stat().st_size < self.handle.tell():
            path=self.path
            self.path=None
            self.select(path)
            return False
        data=self.handle.read(262144)
        if not data:
            return False
        self.pending+=data
        if len(self.pending)>2097152:
            self.pending=b''
            self.value=None
            self.error='oversized/incomplete record'
            return True
        while b'\n' in self.pending:
            # CSV may quote newlines inside raw_json_text.
            end=self.pending.index(b'\n')+1
            while True:
                raw=self.pending[:end]
                try:
                    text=raw.decode('utf-8-sig')
                    if self.mode=='arm':
                        parsed=json.loads(text)
                        value=arm_value(parsed)
                    else:
                        fields=list(csv.reader(io.StringIO(text,newline=''),strict=True))[0]
                        if len(fields)!=len(self.header):
                            raise ValueError('CSV field count')
                        value=omni_value(dict(zip(self.header,fields)))
                    self.pending=self.pending[end:]
                    if value is not None:
                        self.value=value
                        self.error=None
                        self.revision+=1
                        if not initial:
                            self.updated=now
                    break
                except csv.Error as exc:
                    if 'unexpected end of data' in str(exc):
                        next_end=self.pending.find(b'\n',end)
                        if next_end<0:
                            return True
                        end=next_end+1
                        continue
                    self.pending=self.pending[end:]
                    self.value=None
                    self.error=str(exc)
                    break
                except (ValueError,KeyError,TypeError,IndexError,AttributeError) as exc:
                    self.pending=self.pending[end:]
                    self.value=None
                    self.error=str(exc)
                    break
        return True

    def snapshot(self,now):
        value=self.value
        status='WAIT'
        age=None
        if self.error:
            status='INVALID'
        elif value is not None:
            age=now-value['source_monotonic_s']
            if self.updated is None:
                status='HISTORICAL'
            elif age<0:
                status='CLOCK_MISMATCH'
            else:
                status='FRESH_LOG' if age<=.75 and now-self.updated<=.75 else 'STALE'
        return dict(status=status,source_age_s=age,log_revision=self.revision,
                    error=self.error,values=value)

    def close(self):
        if self.handle:
            self.handle.close()


def newest(root, patterns):
    paths=[p for pattern in patterns for p in root.glob(pattern) if p.is_file()]
    return max(paths,key=lambda p:p.stat().st_mtime_ns) if paths else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--arm-log',type=Path)
    parser.add_argument('--omni-csv',type=Path)
    parser.add_argument('--seconds',type=float,default=0)
    args=parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds<0:
        parser.error('seconds must be finite and nonnegative')
    arm,omni=LogTail('arm'),LogTail('omni')
    start=deadline=time.monotonic()
    scan=-math.inf
    count=0
    print('READ ONLY: 50 Hz latest-value display; no UDP/SDK/DDS/G1 output.',flush=True)
    print('ARM=simulation IK rad; OMNI=gateway mapped vx/vy m/s, yaw_rate rad/s. G1_RX=UNVERIFIED.',flush=True)
    print('Joint order per arm: '+','.join(SUFFIXES),flush=True)
    try:
        while not args.seconds or time.monotonic()-start<args.seconds:
            now=time.monotonic()
            if now-scan>=1:
                paths=(args.arm_log or newest(args.root,('logs/test_results/bimanual/unity_*.jsonl',)),
                       args.omni_csv or newest(args.root,('logs/test_results/omni_timeseries/*.csv',
                            'logs/test_results/omni_gateway_readonly/*.csv')))
                for stream,path in zip((arm,omni),paths):
                    if stream.path!=path:
                        print(f'[SOURCE {stream.mode}] {path}',flush=True)
                    stream.select(path)
                scan=now
            arm.poll(now)
            omni.poll(now)
            now=time.monotonic()
            if count==0:
                deadline=now
            print(json.dumps(dict(display_sequence=count,display_monotonic_s=now,
                g1_rx='UNVERIFIED',arm_stage='SIMULATION_IK_NOT_G1_TX',
                omni_stage='MAPPED_LOG_NOT_DELIVERY_ACK',arm=arm.snapshot(now),
                omni=omni.snapshot(now)),allow_nan=False,separators=(',',':')),flush=True)
            count+=1
            deadline+=.02
            delay=deadline-time.monotonic()
            if delay>0:
                time.sleep(delay)
            else:
                deadline=time.monotonic()  # Do not burst old display frames.
    except KeyboardInterrupt:
        print('Monitor closed. Source controllers were not stopped.',flush=True)
    finally:
        arm.close()
        omni.close()


if __name__=='__main__':
    main()
