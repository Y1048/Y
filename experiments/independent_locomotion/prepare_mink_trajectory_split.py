"""Freeze the first recorded PC Mink command train/validation split."""

from pathlib import Path

from mink_trajectory_dataset import build_bank


ROOT = Path("/mnt/c/Users/user/Desktop/G1_Teleop_Project")
SOURCE = ROOT / "logs/test_results"
TRAIN = (
    "cycle_packets_20260909_172802_4706973.jsonl",
    "cycle_packets_20260909_173528_4861648.jsonl",
    "cycle_packets_20260910_093608_4827814.jsonl",
    "cycle_packets_20260910_101529_1211725.jsonl",
    "cycle_packets_20260910_101834_6439046.jsonl",
)
VALIDATION = (
    "cycle_packets_20260910_134342_5029522.jsonl",
    "cycle_packets_20260910_145047_5043584.jsonl",
)


if __name__ == "__main__":
    destination = ROOT / "experiments/independent_locomotion/data"
    build_bank(
        {
            "train": [SOURCE / name for name in TRAIN],
            "validation": [SOURCE / name for name in VALIDATION],
        },
        destination / "mink_command_trajectories_v1.npz",
        destination / "mink_command_trajectories_v1.json",
    )
