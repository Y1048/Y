# GROOT onboard unlimited-duration patch — 2026-10-01

## Why this exists

The Windows integrated launcher can now reproduce the previously proven manual
two-SSH-terminal workflow: each onboard program gets its own forced PTY
(`ssh -tt`) and runs in the foreground.

The current G1 onboard `groot_balance_actuator` still hard-limits
`--duration` to `(0, 300]` seconds and defaults NORMAL mode to 300 seconds.
Therefore unlimited NORMAL runtime requires an onboard source change and
rebuild. This repository does not contain the onboard source tree, so the
change is carried as:

```text
tools/GROOT_ONBOARD_UNLIMITED_DURATION.patch
```

The desktop launcher detects support from
`./build/groot_balance_actuator --help`:

- if `--unlimited-duration` exists: use it;
- otherwise: keep the compatible `--duration 300` fallback.

## Apply on the G1

After pulling `Y1048/Y` on the Windows PC, copy the patch to the G1. Replace
`<G1_HOST>` with the address currently used for SSH.

```powershell
scp .\tools\GROOT_ONBOARD_UNLIMITED_DURATION.patch unitree@<G1_HOST>:~/GROOT_ONBOARD_UNLIMITED_DURATION.patch
```

On the G1:

```bash
cd ~/groot_onboard_runtime

git status
git apply --check ~/GROOT_ONBOARD_UNLIMITED_DURATION.patch
git apply ~/GROOT_ONBOARD_UNLIMITED_DURATION.patch
git diff -- src/g1_balance_actuator.cpp
```

Do not reset or clean unrelated local work.

Rebuild `groot_balance_actuator` using the same CMake build procedure already
used for this onboard runtime. After rebuilding, verify the binary contract:

```bash
./build/groot_balance_actuator --help | grep -F unlimited-duration
```

Expected help text includes `--unlimited-duration`.

## Behavioral contract

The patch changes only the planned NORMAL duration timeout:

- `--duration SEC` keeps the existing `(0, 300]` behavior;
- `--unlimited-duration` is NORMAL-only;
- specifying both is rejected;
- SIGINT/SIGTERM/SIGHUP damping behavior remains active;
- emergency damping paths remain active;
- `--supervisor-off` semantics are unchanged.

The integrated launcher performs normal shutdown in this order:

1. SIGINT the owned `groot_balance_actuator`;
2. wait for controlled damping to complete;
3. SIGINT the owned heading controller;
4. close the SSH sessions;
5. stop the remaining PC-side workers.

For normal shutdown, press Enter in the integrated manager. Do not use the
window close button as the normal stop mechanism while G1 actuation may be
active.
