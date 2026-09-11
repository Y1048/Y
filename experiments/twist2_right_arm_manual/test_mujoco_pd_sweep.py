"""Allowlisted math, original-C++ parity, and headless MuJoCo regressions."""
from __future__ import annotations

import hashlib
import importlib.util
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np

from mujoco_pd_contract import (Contract, ROOT, RATES, RoundTrip, candidate_gains,
                                load_contract, writer_target)


def fixture() -> Contract:
    return Contract(np.zeros(29), np.full(29, 40.), np.full(29, 5.),
                    np.full(29, -2.), np.full(29, 2.), np.full(29, 25.))


class MathTest(unittest.TestCase):
    def test_reference_bounds_and_three_cycles(self):
        path = RoundTrip()
        points = [path.at(float(t)) for t in np.arange(0, path.total, .001)]
        self.assertEqual({p.cycle for p in points}, {0,1,2})
        self.assertLessEqual(max(abs(p.offset) for p in points), path.offset + 1e-12)
        self.assertLessEqual(max(abs(p.velocity) for p in points), path.speed + 1e-12)
        self.assertLessEqual(max(abs(p.acceleration) for p in points), path.acceleration + 1e-12)
        self.assertEqual(path.at(path.total).phase, 6)
        self.assertEqual(path.at(path.total).offset, 0)

    def test_reference_derivatives(self):
        path = RoundTrip()
        for t in (1.2, 1.5, 3.0, 4.5):
            h = 1e-5
            p = path.at(t)
            self.assertAlmostEqual((path.at(t+h).offset-path.at(t-h).offset)/(2*h), p.velocity, places=7)
            self.assertAlmostEqual((path.at(t+h).velocity-path.at(t-h).velocity)/(2*h), p.acceleration, places=7)

    def test_reference_invalid_time(self):
        for t in (-1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                RoundTrip().at(t)

    def test_gains_change_only_proximal_group(self):
        c = fixture()
        p, d = candidate_gains(c, 56, 7)
        np.testing.assert_array_equal(p[:22], c.kp[:22])
        np.testing.assert_array_equal(p[26:], c.kp[26:])
        np.testing.assert_array_equal(d[26:], c.kd[26:])
        np.testing.assert_array_equal(p[22:26], [56]*4)
        np.testing.assert_array_equal(d[22:26], [7]*4)
        np.testing.assert_array_equal(c.kp, [40]*29)

    def test_invalid_gain_pairs(self):
        for p,d in ((0,5),(101,5),(40,0),(40,21),(math.nan,5),(40,math.inf)):
            with self.assertRaises(ValueError):
                candidate_gains(fixture(), p, d)

    def test_writer_slew_and_untouched_input(self):
        c = fixture()
        reference = np.ones(29)
        q = np.zeros(29)
        cmd, limited, slew = writer_target(reference, q, q, q, c.kp, c.kd, c)
        np.testing.assert_allclose(cmd, RATES*.002)
        self.assertFalse(limited.any() or slew.any())
        np.testing.assert_array_equal(reference, np.ones(29))

    def test_writer_matches_scalar_cpp_equations(self):
        c = fixture()
        random = np.random.default_rng(1048)
        for _ in range(100):
            ref, prev, q = random.uniform(-1, 1, (3,29))
            dq = random.uniform(-2, 2, 29)
            p, d = candidate_gains(c, 48, 5)
            got, _, _ = writer_target(ref, prev, q, dq, p, d, c)
            expected = []
            for j in range(29):
                clip = lambda x,lo,hi: max(lo, min(hi, x))
                target = clip(ref[j], prev[j]-RATES[j]*.002, prev[j]+RATES[j]*.002)
                target = clip(target, c.lower[j], c.upper[j])
                target = clip(target, q[j]+(-c.torque[j]*.5+d[j]*dq[j])/p[j],
                              q[j]+(c.torque[j]*.5+d[j]*dq[j])/p[j])
                expected.append(clip(target, c.lower[j], c.upper[j]))
            np.testing.assert_allclose(got, expected, atol=1e-12)

    def test_torque_clamp_can_override_slew_and_is_reported(self):
        c = fixture()
        q = np.zeros(29)
        dq = np.ones(29)*4
        cmd, limited, slew = writer_target(q, q, q, dq, c.kp, c.kd, c)
        self.assertTrue(limited.all() and slew.all())
        np.testing.assert_allclose(c.kp*cmd-c.kd*dq, -c.torque*.5)

    def test_limiter_rejects_invalid_arrays(self):
        c = fixture()
        q = np.zeros(29)
        for bad in (np.zeros(28), np.full(29, math.nan)):
            with self.assertRaises(ValueError):
                writer_target(bad,q,q,q,c.kp,c.kd,c)

    def test_contract_parser_rejects_expressions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"bad.hpp"
            path.write_text("const auto kDefault={danger()};")
            with self.assertRaises(ValueError):
                load_contract(path)

    def test_cpp_reference_parity(self):
        cpp = r'''
#include "pd_small_signal_trial.hpp"
#include <iostream>
#include <iomanip>
int main(){std::array<double,29> q{};PdSmallSignalTrial t(q);
 std::cout<<std::setprecision(17);
 for(int n=0;n*.002<t.Total();++n){double s=n*.002;auto p=t.At(s);
 std::cout<<s<<' '<<p.q[22]<<' '<<p.dq<<' '<<p.ddq<<' '<<p.phase<<' '<<p.cycle<<'\n';}}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"reference.cpp"
            path.write_text(cpp)
            exe = Path(directory)/"reference"
            subprocess.run([os.environ.get("CXX","g++"),"-std=c++17","-Wall","-Wextra","-Werror",
                            "-I",str(Path(__file__).parent),str(path),"-o",str(exe)], check=True, timeout=30)
            run = subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=10)
            path = RoundTrip()
            for line in run.stdout.splitlines():
                t,q,dq,ddq,phase,cycle = map(float,line.split())
                point = path.at(t)
                np.testing.assert_allclose([point.offset,point.velocity,point.acceleration], [q,dq,ddq], atol=2e-12)
                self.assertEqual((point.phase,point.cycle),(phase,cycle))


class SummaryTest(unittest.TestCase):
    @staticmethod
    def row(t, reference=0.1, contact=0):
        r = {"time_s":t,"trial_time_s":t,"phase":5,"cycle":0,"segment":"ready_hold","direction":1,
             "torque_target_limited_arm":0,"hard_clipped_arm":0,"slew_exceeded_arm":0,"contacts":contact}
        for j in range(29):
            r.update({f"ref_{j}": reference,f"cmd_{j}":0.,f"q_{j}":0.,f"dq_{j}":0.,f"actual_tau_{j}":0.})
        return r

    def test_score_uses_original_reference_not_limited_command(self):
        from mujoco_pd_sweep import summarize
        s = summarize([self.row(0),self.row(.002)],True,"",.05)
        self.assertAlmostEqual(s["metrics"]["reference_rmse_joint22_rad"], .1)
        self.assertEqual(s["metrics"]["command_rmse_joint22_rad"], 0)
        self.assertIsNone(s["metrics"]["endpoint_holds"][0]["settling_time_s"])

    def test_contact_and_failed_trials_not_eligible(self):
        from mujoco_pd_sweep import summarize
        self.assertFalse(summarize([self.row(0,contact=1)],True,"",.05)["eligible"])
        self.assertFalse(summarize([self.row(0)],False,"velocity",.05)["eligible"])
        self.assertFalse(summarize([],False,"no_state",.05)["eligible"])

    def test_torque_limited_result_not_eligible(self):
        from mujoco_pd_sweep import summarize
        row = self.row(0)
        row["torque_target_limited_arm"] = 1
        self.assertIn("excessive_torque_limiting", summarize([row],True,"",.05)["exclusion_reasons"])


@unittest.skipUnless(importlib.util.find_spec("mujoco"), "MuJoCo is required for dynamics tests")
class DynamicsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mujoco_pd_sweep import load_model, MODEL
        cls.original = sha = hashlib.sha256(MODEL.read_bytes()).hexdigest()
        cls.model,cls.qadr,cls.vadr,cls.motors,_ = load_model(MODEL,.001)
        cls.contract = load_contract()
        assert sha == hashlib.sha256(MODEL.read_bytes()).hexdigest()

    def test_fixed_pelvis_and_direct_motors(self):
        self.assertEqual((self.model.nq,self.model.nv,self.model.nu),(29,29,29))
        self.assertEqual(len(set(self.qadr)),29)
        self.assertEqual(len(set(self.motors)),29)

    def test_reject_nondivisor_timestep(self):
        from mujoco_pd_sweep import load_model, MODEL
        for dt in (0, math.nan, .003, .0013):
            with self.assertRaises(ValueError):
                load_model(MODEL, dt)

    def test_real_dynamics_repeatability_and_gain_effect(self):
        from mujoco_pd_sweep import run_candidate
        a, ar = run_candidate(self.model,self.qadr,self.vadr,self.motors,self.contract,40,5)
        b, br = run_candidate(self.model,self.qadr,self.vadr,self.motors,self.contract,40,5)
        c, cr = run_candidate(self.model,self.qadr,self.vadr,self.motors,self.contract,56,5)
        self.assertTrue(a["completed"], a)
        self.assertTrue(c["completed"], c)
        self.assertEqual(a,b)
        self.assertEqual(ar,br)
        self.assertGreater(a["metrics"]["reference_rmse_joint22_rad"], 1e-5)
        self.assertNotEqual(a["metrics"]["reference_rmse_joint22_rad"],c["metrics"]["reference_rmse_joint22_rad"])
        self.assertEqual({r["cycle"] for r in ar if r["trial_time_s"]>=0},{0,1,2})
        self.assertGreater(np.ptp([r["q_22"] for r in ar if r["trial_time_s"]>=0]), .05)
        # q is a response, not replayed reference, and nonexcited references stay unchanged.
        for r in ar[::50]:
            np.testing.assert_allclose([r[f"ref_{j}"] for j in range(29) if j!=22],
                                       [self.contract.baseline[j] for j in range(29) if j!=22])

    def test_failing_gain_is_not_ranked(self):
        from mujoco_pd_sweep import run_candidate
        result,_ = run_candidate(self.model,self.qadr,self.vadr,self.motors,self.contract,1,.1)
        self.assertFalse(result["eligible"])
        self.assertFalse(result["completed"])


class PreservationTest(unittest.TestCase):
    def test_live_files_and_pd_reference_unchanged(self):
        expected = {
            "tools/START_TWIST2_MINK_CYCLE_CANDIDATE.ps1":"3ac647adbe3d9a424a439d88afcef79a487cce9f",
            "experiments/twist2_right_arm_manual/twist2_mink_cycle_trial.cpp":"b4ad5bd2207b4398900571e85bf3a98f34de008a",
            "experiments/twist2_right_arm_manual/mink_live_cycle_target.hpp":"b7f6989e4eba143ba9336486f49699e91f76e325",
            "experiments/twist2_right_arm_manual/mink_udp_target.hpp":"69435cfdd33b833a07e0be6159d4da258e73752f",
            "experiments/twist2_right_arm_manual/pd_small_signal_trial.hpp":"ff37fe616bc08d9f1e509ec24be49ae169cd7712"}
        for name, sha in expected.items():
            raw=(ROOT/name).read_bytes().replace(b"\r\n",b"\n")
            # Compatibility snapshot of 27a6134; update intentionally, not to hide a regression.
            self.assertEqual(hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest(),sha,name)


if __name__ == "__main__":
    if os.environ.get("G1_REQUIRE_MUJOCO") == "1" and not importlib.util.find_spec("mujoco"):
        raise SystemExit("MuJoCo required: refusing a skipped dynamics suite")
    unittest.main()
