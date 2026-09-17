# G1 velocity policy + Unity keypad + Mink right arm

This candidate keeps one full-body `rt/lowcmd` owner. The TWIST2 static-stand
policy owns leg joints 0..11 while the keypad command is zero. A nonzero keypad
target starts a checked blend to the velocity policy; keypad `5` settles the
gait and blends back to static stand without stopping the LowCmd writer. The waist is held and
the existing Mink cycle target owns right-arm joints 22..28. The prior
lower-body and right-arm projects are not modified.

Unity numeric keypad mapping:

- Each `8` / `2` press adds / subtracts 0.2 m/s longitudinal velocity.
- Each `4` / `6` press adds / subtracts 0.2 m/s lateral velocity.
- Each `7` / `9` press adds / subtracts 0.2 rad/s yaw velocity.
- All three axes latch after key release and clamp to `[-0.8, 0.8]`.
- `5` alone resets all three commanded velocities to zero.

Unity sends only to `127.0.0.1:5016`. The Python relay validates it and forwards
to G1 UDP 5017. Mink continues through localhost 5008 to G1 UDP 5014. A single
random token binds both relays to the G1 process. Key release retains the
latched velocity; a `5` press sends zero. A
velocity stream timeout also requests zero velocity. The velocity policy
remains the active leg owner before and after measured arm initialization
reaches `udp_ready`. After the initial full-body takeover blend, operator
velocity is accepted independently of arm readiness. A stale stream sets the
target to zero while the continuous gait phase keeps advancing.
Leg commands retain a 0.08 rad range margin, increased to 0.12 rad for both
ankle-roll joints.

The discarded fixed-joint idle candidate lost balance immediately after the
motion service handoff on 2026-09-14. Do not replace a balancing policy with a
captured joint-position hold.

The binary is command-capable. Building or checksum inspection does not move the
robot. Running `run_velocity_mink_keypad.sh` initializes DDS and can actuate it.

`run_static_stand_handoff_probe.sh` and `--handoff-only-trial` are blocked. The
2026-09-14 physical probe stopped LowCmd before Regular/AI ownership was
verified, which removed actuator support. The program now rejects that option
before constructing the DDS controller. Completed PD sweeps also retain the
current LowCmd owner and do not call the unverified Regular handoff routine.

The periodic CSV includes `leg_policy_mode` (`twist2`, `to_velocity`,
`velocity`, `settle`, or `to_twist2`) so a recorded run identifies which policy
produced each 50 Hz leg target.
