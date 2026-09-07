"""Paths, seeds and locked constants for SPEC v1 (+ Amendment 1).

Nothing here is a research decision; every value traces to the SPEC.
"""
from pathlib import Path

# --- roots -------------------------------------------------------------
# Data lives outside the public repo and is never committed. `data` in the
# repo root is a gitignored symlink to STUDY_ROOT/data.
STUDY_ROOT = Path.home() / "Desktop" / "forecast-study"
REPO_ROOT = Path(__file__).resolve().parent.parent

DATASETS_REPO = STUDY_ROOT / "forecastbench-datasets" / "datasets"
PROCESSED = STUDY_ROOT / "data" / "raw" / "forecastbench-processed-forecast-sets"
DERIVED = STUDY_ROOT / "data" / "derived"

DOCS = REPO_ROOT / "docs"
FIGDIR = DOCS / "figures"

# --- the round (SPEC 2.2) ---------------------------------------------
ROUND = "2024-07-21"
DUE_DATE = "2024-07-21"

HUMAN_FILES = {
    "S": DATASETS_REPO / "forecast_sets" / ROUND / f"{ROUND}.ForecastBench.human_super_individual.json",
    "P": DATASETS_REPO / "forecast_sets" / ROUND / f"{ROUND}.ForecastBench.human_public_individual.json",
}
RESOLUTION_SET = DATASETS_REPO / "resolution_sets" / f"{ROUND}_resolution_set.json"
MODEL_DIR = PROCESSED / ROUND

# --- provenance (data/PROVENANCE.md) -----------------------------------
DATASETS_COMMIT = "68932db171f5e13349d9bda0dd9f96fcf6e227e2"
TARBALL_SHA256 = {
    "forecast_sets.tar.gz": "219998293a577c820dfa4fdc34541833bd99fd47b60854c2e0424c1a38490b45",
    "processed_forecast_sets.tar.gz": "7f20d24b16b5cacc0c9f1b4f09245aedb17f789504810402ba2458c6ca3486c7",
}

# --- locked parameters (SPEC 11, Amendment 1) --------------------------
MARKET_SOURCES = {"manifold", "metaculus", "polymarket", "infer", "kalshi"}

# Amendment 1 B.3: matched information condition = freeze values, no news.
# Both scaffolds qualify -> 17 base models x 2 scaffolds = 34 variants.
MATCHED_SCAFFOLDS = ("zero shot with freeze values", "scratchpad with freeze values")

CLIP = (0.01, 0.99)          # SPEC 5.2, 7.2
PILOT_FRACTION = 0.30        # SPEC 11
PILOT_SEED = 20260907        # SPEC 11 / Amendment 1 E.1 (30% of QUESTIONS)
SPLIT_HALF_SEED = 20260906   # SPEC 11 (H5 only; not run in the pilot)
BOOTSTRAP_DRAWS = 2000       # SPEC 11 (H5 only)
IMPUTED_ELIGIBILITY_MAX = 0.05   # Amendment 1 A.3
SD_DDOF = 1                  # sample SD for DIS
