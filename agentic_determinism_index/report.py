"""Turn a run directory of raw transcripts into scores.json + SCORES.md."""
import glob
import json
import os

from .metrics import score_samples


def score_run(run_dir):
    rows = []
    for path in sorted(glob.glob(os.path.join(run_dir, "probes", "*.json"))):
        with open(path) as f:
            probe = json.load(f)
        m = score_samples(probe["samples"], probe["case"].get("expect", "text"))
        row = {
            "provider": probe["target"]["provider"],
            "model": probe["target"]["model"],
            "case": probe["case"]["id"],
            **m,
        }
        if probe["target"].get("label"):
            row["label"] = probe["target"]["label"]
        rows.append(row)
    return rows


def markdown(rows):
    cols = ["label", "provider", "model", "case", "n_ok", "errors", "distinct",
            "mode_share", "first_divergence_char", "byte_identical", "tool_call_rate"]
    # Drop the label column when no row carries one (keeps older runs tidy).
    if not any(r.get("label") for r in rows):
        cols = [c for c in cols if c != "label"]
    lines = ["| " + " | ".join(cols) + " |",
             "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines) + "\n"
