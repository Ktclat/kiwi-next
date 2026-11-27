#!/usr/bin/env python3
"""Compare unique completed outputs, not Ninja's changing action denominator."""
import argparse
from pathlib import Path


def read_outputs(path: Path) -> dict[str, int]:
    outputs: dict[str, int] = {}
    with path.open(encoding="utf-8") as log:
        if log.readline().strip() not in {"# ninja log v5", "# ninja log v6", "# ninja log v7"}:
            raise ValueError(f"Unsupported Ninja log format: {path.name}")
        for line in log:
            if not line.endswith("\n"):
                continue  # The last record may have been interrupted.
            start, end, _mtime, name, _command = line.rstrip("\n").split("\t")
            if not (0 <= int(start) <= int(end)) or not name:
                raise ValueError(f"Invalid Ninja log record in {path.name}")
            # Count each output only once, from when it was first completed.
            outputs[name] = min(outputs.get(name, int(end)), int(end))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed", type=Path)
    parser.add_argument("restore", type=Path)
    args = parser.parse_args()
    seed = read_outputs(args.seed)
    restore = read_outputs(args.restore)
    if not seed or not restore:
        parser.error("Both builds must record completed outputs")
    shared = sorted(restore[name] for name in seed.keys() & restore.keys())
    cutoff = (95 * len(seed) + 99) // 100
    new = len(restore) - len(shared)
    delta = len(restore) - len(seed)
    print(
        f"Completed unique Ninja outputs: seed {len(seed)}, restore {len(restore)} "
        f"({delta:+d} net), {len(shared)} shared, {new} new on restore."
    )
    print(
        f"Restore reached 95% of the seed outputs after {shared[cutoff-1]/1000:.1f}s."
        if len(shared) >= cutoff else "Restore did not reach 95% of the seed outputs."
    )
    if len(shared) < cutoff or delta < max(100, (len(seed) + 19) // 20):
        print("APK continuation did not clear the minimum progress threshold.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
