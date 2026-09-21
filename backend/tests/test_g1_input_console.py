import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

PATH=Path(__file__).resolve().parents[2]/'tools/PRINT_G1_INPUTS_50HZ.py'
spec=importlib.util.spec_from_file_location('input_console',PATH)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def arm_row(t=10):
    return dict(kind='state',schema='g1.bimanual.unity.sim.state.v1',simulation_only=True,
                joint_names=m.JOINTS,q_rad=[i/100 for i in range(14)],monotonic_s=t,
                state='tracking',sequence=7,feedback_sequence=8,session='fixture')


class ConsoleTests(unittest.TestCase):
    def test_order_units_and_invalid_data(self):
        self.assertEqual(m.arm_value(arm_row())['right_q_rad'],[i/100 for i in range(7,14)])
        for field,value in [('q_rad',[float('nan')]*14),('q_rad',[True]*14),
                            ('joint_names',list(reversed(m.JOINTS))),('simulation_only',False)]:
            row=arm_row();row[field]=value
            with self.assertRaises(ValueError):m.arm_value(row)

    def test_partial_history_fresh_stale_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'arm.jsonl'
            path.write_text(json.dumps(arm_row())+'\n')
            tail=m.LogTail('arm')
            try:
                tail.select(path)
                self.assertEqual(tail.snapshot(10)['status'],'HISTORICAL')
                raw=json.dumps(arm_row(11)).encode()+b'\n'
                with path.open('ab') as f:f.write(raw[:50])
                tail.poll(11)
                self.assertEqual(tail.snapshot(11)['status'],'HISTORICAL')
                with path.open('ab') as f:f.write(raw[50:])
                tail.poll(11.01)
                self.assertEqual(tail.snapshot(11.02)['status'],'FRESH_LOG')
                self.assertEqual(tail.snapshot(12)['status'],'STALE')
                with path.open('ab') as f:f.write(b'{broken}\n')
                tail.poll(12)
                self.assertEqual(tail.snapshot(12)['status'],'INVALID')
                self.assertIsNone(tail.snapshot(12)['values'])
            finally:tail.close()

    def test_omni_quoted_multiline_and_fragment(self):
        row=dict(schema='g1.omni.timeseries.v1',receive_monotonic_s='20',sample_sequence='8',
                 calibrated='1',mx='.2',my='.3',arm_yaw_deg='110',omni_yaw_rate_deg_s='2',
                 vx='.1',vy='-.2',yaw_rate='.4',yaw_diff_deg='5',yaw_step_diff_deg='1',
                 raw_json_text='{\n"movementXY":[0.2,0.3]}')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'omni.csv'
            header=io.StringIO(newline='');csv.writer(header).writerow(row.keys())
            path.write_text(header.getvalue())
            tail=m.LogTail('omni')
            try:
                tail.select(path)
                content=io.StringIO(newline='');csv.writer(content).writerow(row.values())
                raw=content.getvalue().encode();cut=raw.index(b'\n')+1
                with path.open('ab') as f:f.write(raw[:cut])
                tail.poll(20)
                self.assertIsNone(tail.value)
                with path.open('ab') as f:f.write(raw[cut:])
                tail.poll(20.01)
                self.assertEqual(tail.value['yaw_rate'],.4)
                self.assertEqual(tail.value['vy'],-.2)
                self.assertEqual(tail.snapshot(20.02)['status'],'FRESH_LOG')
            finally:tail.close()
        row['vx']='nan'
        with self.assertRaises(ValueError):m.omni_value(row)

    def test_no_network_or_process_control_imports(self):
        import ast
        imports=[]
        for node in ast.walk(ast.parse(PATH.read_text())):
            if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
            if isinstance(node,ast.ImportFrom):imports.append(node.module)
        self.assertFalse(set(imports)&{'socket','subprocess','ctypes','websocket','unitree_sdk2py'})


if __name__=='__main__':unittest.main()
