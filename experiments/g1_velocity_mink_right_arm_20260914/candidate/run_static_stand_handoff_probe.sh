#!/usr/bin/env bash
set -euo pipefail

echo "BLOCKED: the 2026-09-14 physical probe stopped LowCmd before Regular/AI ownership was verified, and actuator support was lost." >&2
echo "Do not run --handoff-only-trial. The robot must remain in Regular/AI mode." >&2
exit 1
