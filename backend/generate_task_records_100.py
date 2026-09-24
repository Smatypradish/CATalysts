"""Generate data/task_records_100.csv — the expanded task-time training dataset.

WHAT IT DOES
------------
1. Reads the 5 Caterpillar-supplied rows from data/task_records.csv and copies
   them VERBATIM into the output with Source="dataset". The supplied file is
   never modified, overwritten or deleted.
2. Adds 95 clearly-labelled synthetic rows (Task IDs S001-S095, Source="synthetic")
   so the ML prototype has 100 task-history records in total.
3. Writes data/task_records_100.csv with the original columns plus a "Source"
   provenance column, then re-reads the file and asserts:
     - 100 rows total, 5 dataset + 95 synthetic
     - the 5 embedded dataset rows are identical to data/task_records.csv

SYNTHETIC GENERATION FORMULA (documented, deterministic, seeded RNG)
--------------------------------------------------------------------
    base        = BASE_MINUTES[task_type]          # typical duration, ideal conditions
    age_factor  = 1 + 0.015 * machine_age          # older machines run slower
    actual      = base * WEATHER_FACTOR[weather] * SKILL_FACTOR[skill] * age_factor
                  * uniform(0.97, 1.03)            # per-row jitter (site conditions)
                  + gauss(0, 4)                    # additive noise (minutes)
    estimated   = base * WEATHER_FACTOR[weather] * age_factor
                  * uniform(0.95, 1.08)            # planner estimate: ignores operator
                                                   # skill and has its own error
Rationale: weather, operator skill and machine age are the physical drivers the
model is allowed to learn from; the planner estimate deliberately ignores skill,
so Estimated Time is NOT a leak-free proxy for Actual Time (and the model never
uses it as an input feature).

Coverage: all 5 task types x 4 weather conditions x 3 skill levels (60 combos)
appear at least once; the remaining 35 rows are random combos with random
machine ages (1-10 years), so no value set is simply copied repeatedly.

Run:  python backend/generate_task_records_100.py   (from the project root)
Deterministic: random.Random(42) — re-running produces the identical file.
"""
import random
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
SRC_CSV = DATA_DIR / "task_records.csv"          # supplied Dataset 2 (NEVER modified)
OUT_CSV = DATA_DIR / "task_records_100.csv"      # expanded 100-row prototype dataset

# Documented generation formula constants.
BASE_MINUTES = {"Earth Excavation": 55, "Trenching": 50, "Material Loading": 35,
                "Grading": 40, "Demolition": 85}
WEATHER_FACTOR = {"Sunny": 1.00, "Cloudy": 1.08, "Rainy": 1.22, "Windy": 1.15}
SKILL_FACTOR = {"Expert": 0.92, "Intermediate": 1.05, "Beginner": 1.22}

N_SYNTHETIC = 95


def make_synthetic_rows(rng: random.Random) -> list[dict]:
    """95 labelled synthetic records: full combo coverage + random fill."""
    rows = []
    combos = [(t, w, s) for t in BASE_MINUTES for w in WEATHER_FACTOR
              for s in SKILL_FACTOR]
    rng.shuffle(combos)
    # Every task/weather/skill combination once, then random combos to reach 95.
    picks = combos + [(rng.choice(list(BASE_MINUTES)),
                       rng.choice(list(WEATHER_FACTOR)),
                       rng.choice(list(SKILL_FACTOR)))
                      for _ in range(N_SYNTHETIC - len(combos))]
    for n, (ttype, weather, skill) in enumerate(picks, start=1):
        base = BASE_MINUTES[ttype]
        age = rng.randint(1, 10)
        age_factor = 1 + 0.015 * age
        actual = (base * WEATHER_FACTOR[weather] * SKILL_FACTOR[skill] * age_factor
                  * rng.uniform(0.97, 1.03) + rng.gauss(0, 4))
        estimated = base * WEATHER_FACTOR[weather] * age_factor * rng.uniform(0.95, 1.08)
        rows.append({
            "Task ID": f"S{n:03d}", "Task Type": ttype, "Weather": weather,
            "Operator Skill": skill, "Machine Age (yrs)": age,
            "Estimated Time (min)": round(estimated, 1),
            "Actual Time (min)": round(max(actual, 5.0), 1),
            "Source": "synthetic",
        })
    return rows


def main():
    rng = random.Random(42)

    # 1. Original Caterpillar rows, copied VERBATIM at text level from the
    #    supplied file (only the ",dataset" provenance tag is appended).
    #    The supplied file itself is never modified.
    raw_lines = SRC_CSV.read_text(encoding="utf-8-sig").splitlines()
    header = raw_lines[0]
    orig_rows = [line for line in raw_lines[1:] if line.strip()]
    assert len(orig_rows) == 5, f"expected 5 supplied rows, found {len(orig_rows)}"

    # 2. Synthetic rows.
    synthetic = make_synthetic_rows(rng)
    assert len(synthetic) == N_SYNTHETIC

    # 3. Write the combined 100-row dataset.
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        f.write(header + ",Source\n")
        for line in orig_rows:                       # verbatim originals
            f.write(line + ",dataset\n")
        for r in synthetic:                          # labelled synthetic rows
            f.write(",".join([
                r["Task ID"], r["Task Type"], r["Weather"], r["Operator Skill"],
                str(r["Machine Age (yrs)"]),
                f"{r['Estimated Time (min)']:.1f}",
                f"{r['Actual Time (min)']:.1f}",
                r["Source"],
            ]) + "\n")
    print(f"wrote {OUT_CSV} (5 verbatim originals + {N_SYNTHETIC} synthetic)")

    # 4. Self-verification: re-read and prove originals are unchanged.
    check = pd.read_csv(OUT_CSV)
    embedded = (check[check["Source"] == "dataset"]
                .drop(columns=["Source"]).reset_index(drop=True))
    pd.testing.assert_frame_equal(embedded, pd.read_csv(SRC_CSV), check_dtype=False)
    counts = check["Source"].value_counts().to_dict()
    assert counts == {"synthetic": 95, "dataset": 5}, counts
    assert check["Task ID"].is_unique
    print("verified: 100 rows = 5 dataset (verbatim originals) + 95 synthetic")
    print("per task type:", check["Task Type"].value_counts().to_dict())


if __name__ == "__main__":
    main()
