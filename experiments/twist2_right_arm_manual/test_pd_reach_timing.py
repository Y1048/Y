import unittest
import numpy as np
from numpy.polynomial import Polynomial
from pd_reach_timing import make_timing, choose_timing, check_acceleration


class TimingTests(unittest.TestCase):
    def test_duration_selected_from_fixed_limits(self):
        result=choose_timing([Polynomial([0,1])])
        self.assertNotEqual(result[1][-1],2.0)
        self.assertLessEqual(result[-1]['checked_peak_speed_rad_s'],np.pi/4)
        self.assertLessEqual(result[-1]['checked_peak_acceleration_rad_s2'],10)

    def test_acceleration_cap(self):
        check_acceleration(9.4642)
        check_acceleration(10.0)
        for peak in (10.0001, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):check_acceleration(peak)

    def test_linear_path_endpoints_monotonic_speed(self):
        curve,t,u,v,info=make_timing([Polynomial([0,1])],2)
        fine=np.linspace(0,2,20001)
        self.assertEqual(u[0],0)
        self.assertEqual(u[-1],1)
        self.assertEqual(v[0],0)
        self.assertEqual(v[-1],0)
        self.assertTrue(np.all(np.diff(curve(fine))>=0))
        self.assertLess(np.max(curve(fine,1)),np.pi/4)
        self.assertGreater(info['ramp_seconds'],0)

    def test_unattainable_duration_rejected(self):
        with self.assertRaisesRegex(ValueError,'lower bound'):
            make_timing([Polynomial([0,1])],1)

    def test_invalid_time_and_stationary_path(self):
        for seconds in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):make_timing([Polynomial([0,1])],seconds)
        with self.assertRaisesRegex(ValueError,'stationary'):
            make_timing([Polynomial([1])],2)


if __name__=='__main__':unittest.main()
