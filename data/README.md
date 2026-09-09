# data

Synthetic 8-system world. Extracts are not committed — regenerate byte-identically:

    uv run python data/generate_world.py --seed 42 --out data/extracts

Committed ground truth in `ground_truth/`: `crosswalk.csv` (every system-local id -> true entity), `anomalies.json` (12 injected anomalous providers, 4 signatures), `er_traps.json` (deliberate entity-resolution traps). See docs/data-dictionary.md.
Synthetic data only; see CLAUDE.md hard rules.
