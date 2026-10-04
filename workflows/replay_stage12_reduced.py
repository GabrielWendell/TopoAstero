"""Recompute compact models/paired predictions from archived features; no holdout."""

import argparse
from pathlib import Path

import numpy as np

from topoastero.hybrid.features import load_config, matrix
from topoastero.hybrid.models import nested_predict
from topoastero.population_store import contained, read_json, read_table


def replay(root: Path) -> int:
    cfg = load_config(root)
    output = contained(root, cfg["output"])
    rows = read_json(output / "feature_dataset.json")["rows"]
    archived = read_table(output / "oof_predictions.csv")
    if not rows:
        raise ValueError("no observed development feature rows")
    groups = [r["stable_star_id"] for r in rows]
    for method in ("baseline", "hybrid"):
        for quantity in ("numax", "dnu"):
            model = read_json(output / "models.json")["models"][method + "_" + quantity]
            labels = np.array([np.log(r["targets"][quantity] / r["classical"][quantity]) for r in rows])
            oof, _, _ = nested_predict(matrix(rows, model["features"]), labels, groups, cfg)
            for row, point in zip(rows, oof, strict=True):
                expected = next(r for r in archived if r["stable_star_id"] == row["stable_star_id"] and r["quantity"] == quantity)
                value = row["classical"][quantity] * np.exp(point["prediction"])
                if not np.isclose(value, float(expected[method]), rtol=1e-9, atol=1e-8):
                    raise ValueError("archived OOF prediction does not replay")
    return len(groups)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    print(f"Stage 12 reduced replay: PASS ({replay(parser.parse_args().root.resolve())} stars); no raw transfer or holdout opened")
