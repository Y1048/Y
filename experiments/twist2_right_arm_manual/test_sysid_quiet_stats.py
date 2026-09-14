import tempfile
import unittest
from pathlib import Path
import sysid_quiet_stats as stats
from test_sysid_readonly import row,save

class QuietStatsTests(unittest.TestCase):
    def test_measured_summary_never_recommends_gains(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'q.jsonl';save(p,[row(0,False),row(1,False)])
            result=stats.summarize([p]);self.assertFalse(result['fit_ready'])
            self.assertIsNone(result['recommended_hardware_gains'])
            self.assertEqual(len(result['episodes'][0]['joint_q_std_rad']),29)

if __name__=='__main__':unittest.main()
