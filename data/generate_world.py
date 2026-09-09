#!/usr/bin/env python
"""Build the synthetic 8-system world and freeze it to disk.

    uv run python data/generate_world.py --seed 42 --out data/extracts

Writes ``data/extracts/{system}.jsonl`` for the eight source systems and the committed
ground truth (crosswalk, anomaly registry, ER-trap registry) to ``data/ground_truth/``.
Deterministic: the same seed reproduces byte-identical files.

All data is synthetic (CLAUDE.md hard rule 1) and the systems are named only by class
(hard rule 2).
"""

import argparse
from pathlib import Path

from pipeline.worldgen.extracts import SYSTEMS, build_extracts, write_extracts
from pipeline.worldgen.ground_truth import write_ground_truth
from pipeline.worldgen.world import SIGNATURES, TRAP_KINDS, build_world

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "data" / "extracts"
GROUND_TRUTH_DIR = REPO_ROOT / "data" / "ground_truth"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="directory for the eight per-system JSONL extracts",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=GROUND_TRUTH_DIR,
        help="directory for crosswalk.csv / anomalies.json / er_traps.json",
    )
    parser.add_argument("--providers", type=int, default=160, help="provider count")
    parser.add_argument("--members", type=int, default=2400, help="member count")
    return parser.parse_args(argv)


def _mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    world = build_world(args.seed, n_providers=args.providers, n_members=args.members)
    bundle = build_extracts(world)
    extract_counts = write_extracts(bundle, args.out)
    truth_counts = write_ground_truth(world, bundle, args.ground_truth)

    denied = sum(1 for event in world.claims if event.denied)
    print(f"Enterprise Intelligence Graph — synthetic world (seed {args.seed})")
    print(
        f"  providers {len(world.providers):,}   members {len(world.members):,}   "
        f"claim lines {len(world.claims):,}   denied {denied:,} "
        f"({denied / max(1, len(world.claims)):.1%})"
    )

    total_mb = 0.0
    print(f"\nextracts -> {args.out}")
    for system in SYSTEMS:
        path = args.out / f"{system}.jsonl"
        size = _mb(path)
        total_mb += size
        print(f"  {system:<16} {extract_counts[system]:>8,} rows  {size:>7.2f} MB")
    print(f"  {'TOTAL':<16} {sum(extract_counts.values()):>8,} rows  {total_mb:>7.2f} MB")

    print(f"\nground truth -> {args.ground_truth}")
    for name, count in truth_counts.items():
        path = args.ground_truth / name
        total_mb += _mb(path)
        print(f"  {name:<16} {count:>8,} rows  {_mb(path):>7.2f} MB")

    print("\nanomalies by signature:")
    for signature in SIGNATURES:
        hits = [a for a in world.anomalies if a.signature == signature]
        entities = ", ".join(a.entity_id for a in hits)
        print(f"  {signature:<20} {len(hits):>2}   {entities}")

    print("\nER traps by kind:")
    for kind in TRAP_KINDS:
        hits = [trap for trap in world.traps if trap.kind == kind]
        affected = sorted({entity for trap in hits for entity in trap.entity_ids})
        print(f"  {kind:<22} {len(hits):>2} entries  {len(affected):>2} providers")

    print(f"\ntotal on disk: {total_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
