"""Observe actual contact pairs/forces in the unchanged offline PD experiment.

Diagnostic only. Does not suppress collisions, change the ranking policy,
modify a model file, import SDK/DDS, or connect to any robot.
"""
from __future__ import annotations

import json
import sys
import numpy as np

from mujoco_pd_sweep import MODEL, load_model, load_contract, run_candidate


def main() -> None:
    import mujoco
    model, qadr, vadr, motors, _ = load_model(MODEL, .001)
    pairs = {}
    steps = 0
    original_step = mujoco.mj_step

    def observed_step(m, d):
        nonlocal steps
        original_step(m, d)
        steps += 1
        for index in range(d.ncon):
            contact = d.contact[index]
            ids = tuple(map(int, contact.geom))
            body_ids = [int(m.geom_bodyid[g]) for g in ids]
            names = [mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b) for b in body_ids]
            wrench = np.zeros(6)
            if contact.efc_address >= 0:
                mujoco.mj_contactForce(m, d, index, wrench)
            key = ':'.join(map(str, ids))
            record = pairs.setdefault(key, {
                'geoms': list(ids), 'bodies': names,
                'occurrences': 0, 'active_occurrences': 0,
                'min_distance_m': float(contact.dist), 'max_distance_m': float(contact.dist),
                'peak_force_n': 0., 'peak_torque_nm': 0., 'exclude_values': []})
            record['occurrences'] += 1
            record['active_occurrences'] += int(contact.efc_address >= 0)
            record['min_distance_m'] = min(record['min_distance_m'], float(contact.dist))
            record['max_distance_m'] = max(record['max_distance_m'], float(contact.dist))
            record['peak_force_n'] = max(record['peak_force_n'], float(np.linalg.norm(wrench[:3])))
            record['peak_torque_nm'] = max(record['peak_torque_nm'], float(np.linalg.norm(wrench[3:])))
            if int(contact.exclude) not in record['exclude_values']:
                record['exclude_values'].append(int(contact.exclude))

    # Instrument mj_step only in this single-purpose process and restore it
    # even if the original experiment fails. No alternate controller is used.
    mujoco.mj_step = observed_step
    try:
        result, _ = run_candidate(model, qadr, vadr, motors, load_contract(), 40, 5)
    finally:
        mujoco.mj_step = original_step
    print('CONTACT_DIAGNOSTIC ' + json.dumps({
        'schema': 'g1.mujoco.pd.contacts.v1', 'simulation_only': True,
        'physics_steps': steps, 'completed': result['completed'],
        'eligible': result['eligible'], 'pairs': list(pairs.values())}, allow_nan=False))


if __name__ == '__main__':
    def block_network(event, args):
        if event.startswith('socket.'):
            raise RuntimeError('Offline diagnostic forbids networking: ' + event)
    sys.addaudithook(block_network)
    main()
