"""Load ForecastBench round 2024-07-21 and build the analysis frame.

Implements SPEC v1 §2-§4 as amended by Amendment 1 (A join/key handling,
A.3 imputed exclusion, B selection set, B.3 information condition,
C.1 DIS definition).
"""
import json
import re
from datetime import date

import numpy as np
import pandas as pd

import config as C


# ---------------------------------------------------------------- helpers
def _norm_date(x):
    """Amendment 1 A.1: normalise any date-ish string to a calendar date."""
    return None if x is None else str(x)[:10]


def _is_market(source):
    return source in C.MARKET_SOURCES


def parse_model(name):
    """Split 'GPT-4o (zero shot with freeze values)' -> (base, scaffold)."""
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", name)
    if not m:
        return name, None
    return m.group(1).strip(), m.group(2).strip()


# ------------------------------------------------------------ resolutions
def load_resolutions():
    """Return (res_by_target, res_by_question) for single (non-combo) questions."""
    d = json.loads(C.RESOLUTION_SET.read_text())["resolutions"]
    by_target, by_question = {}, {}
    for r in d:
        if isinstance(r["id"], list):
            continue  # combination question; excluded everywhere (Amendment 1 A.2)
        k = (r["source"], r["id"], _norm_date(r["resolution_date"]))
        by_target[k] = r
        by_question.setdefault((r["source"], r["id"]), []).append(r)
    return by_target, by_question


# ----------------------------------------------------------------- humans
def load_humans(res_by_target, res_by_question):
    """Individual human forecasts, one row per forecaster x target.

    Amendment 1 A.1: market rows carry resolution_date = null; fill from the
    resolution set by (source, id). Questions with no resolution row are
    unresolved and drop (SPEC 2.2).
    """
    rows, dropped = [], {"unmappable_market": 0, "unresolved": 0}
    invalid = []          # p_h outside [0, 1]; not anticipated by the SPEC
    for grp, path in C.HUMAN_FILES.items():
        for f in json.loads(path.read_text())["forecasts"]:
            src, qid = f["source"], f["id"]
            rd = _norm_date(f["resolution_date"])
            if rd is None:                                  # market question
                cand = res_by_question.get((src, qid), [])
                if len(cand) != 1:
                    dropped["unmappable_market"] += 1
                    continue
                rd = _norm_date(cand[0]["resolution_date"])
            r = res_by_target.get((src, qid, rd))
            if r is None or not r["resolved"]:
                dropped["unresolved"] += 1
                continue
            ph = float(f["forecast"])
            rec = dict(group=grp, forecaster=f["user_id"], source=src, qid=qid,
                       res_date=rd, p_h=ph, o=float(r["resolved_to"]))
            # A forecast must be a probability. ForecastBench did not clean the
            # public survey's free-entry field: a small number of rows carry
            # values outside [0, 1] (the survey asked for 0-100 and divided by
            # 100, so these are mis-entries, e.g. 104 -> 1.04). The SPEC does
            # not anticipate this; see the report. Excluded, and counted.
            if not (0.0 <= ph <= 1.0) or not np.isfinite(ph):
                invalid.append(rec)
                continue
            rows.append(rec)
    df = pd.DataFrame(rows)
    df["question"] = df["source"] + "|" + df["qid"]
    df["target"] = df["question"] + "|" + df["res_date"]
    inv = pd.DataFrame(invalid)
    if len(inv):
        inv["question"] = inv["source"] + "|" + inv["qid"]
        inv["target"] = inv["question"] + "|" + inv["res_date"]
    return df, dropped, inv


# ----------------------------------------------------------------- models
def load_matched_models():
    """Long frame of the 34 matched-condition model variants (Amendment 1 B.3).

    Combination questions are dropped here (Amendment 1 A.2). `imputed` is
    retained so callers can apply A.3 exclusions and report shares.
    """
    recs, meta = [], []
    for path in sorted(C.MODEL_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        base, scaffold = parse_model(d["model"])
        if scaffold not in C.MATCHED_SCAFFOLDS:
            continue
        meta.append(dict(model=d["model"], base=base, scaffold=scaffold,
                         org=d.get("model_organization"), file=path.name))
        for x in d["forecasts"]:
            if isinstance(x["id"], list):
                continue
            recs.append((d["model"], base, scaffold, x["source"], x["id"],
                         _norm_date(x["resolution_date"]), float(x["forecast"]),
                         bool(x.get("imputed", False)), bool(x["resolved"]),
                         float(x["resolved_to"])))
    df = pd.DataFrame.from_records(
        recs, columns=["model", "base", "scaffold", "source", "qid", "res_date",
                       "p", "imputed", "resolved", "resolved_to"])
    df["question"] = df["source"] + "|" + df["qid"]
    df["target"] = df["question"] + "|" + df["res_date"]
    return df, pd.DataFrame(meta)


# ------------------------------------------------------- baseline (a)
def select_baseline_a(models, human_targets, restrict_single=True):
    """SPEC §4 as amended (B.1 single questions only, A.3 imputed rules).

    Returns (ranking_df, chosen_model, selection_targets, diagnostics).
    `restrict_single` False reproduces the unrestricted-set diagnostic
    (Amendment 1 B.1) -- here it means "include combination targets", which
    this loader has already dropped, so the caller supplies them separately.
    """
    res = models[models["resolved"]]
    sel_targets = sorted(set(res["target"]) - set(human_targets))
    sel = res[res["target"].isin(sel_targets)].copy()
    sel["bs"] = (sel["p"] - sel["resolved_to"]) ** 2

    n_sel = len(sel_targets)
    g = sel.groupby("model")
    rank = pd.DataFrame({
        "n_targets": g.size(),
        "n_imputed": g["imputed"].sum(),
    })
    rank["imputed_share"] = rank["n_imputed"] / n_sel
    ok = sel[~sel["imputed"]]
    rank["n_scored"] = ok.groupby("model").size()
    rank["brier"] = ok.groupby("model")["bs"].mean()
    rank["eligible"] = rank["imputed_share"] <= C.IMPUTED_ELIGIBILITY_MAX
    rank = rank.sort_values("brier")
    elig = rank[rank["eligible"]]
    chosen = elig.index[0]
    return rank, chosen, sel_targets


# ------------------------------------------------------------------- DIS
def unrestricted_champion(human_targets):
    """Diagnostic (Amendment 1 B.1): who wins on the UNRESTRICTED selection set
    (single + combination targets), which the amendment rules out for the
    real baseline. Combination keys include `direction`.
    """
    recs = []
    for path in sorted(C.MODEL_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        base, scaffold = parse_model(d["model"])
        if scaffold not in C.MATCHED_SCAFFOLDS:
            continue
        for x in d["forecasts"]:
            if isinstance(x["id"], list):
                tgt = ("COMBO|" + x["source"] + "|" + json.dumps(x["id"]) + "|"
                       + json.dumps(x["direction"]) + "|" + _norm_date(x["resolution_date"]))
            else:
                tgt = (x["source"] + "|" + x["id"] + "|" + _norm_date(x["resolution_date"]))
            recs.append((d["model"], tgt, float(x["forecast"]),
                         bool(x.get("imputed", False)), bool(x["resolved"]),
                         float(x["resolved_to"])))
    df = pd.DataFrame.from_records(
        recs, columns=["model", "target", "p", "imputed", "resolved", "resolved_to"])
    res = df[df["resolved"] & ~df["target"].isin(human_targets)].copy()
    res["bs"] = (res["p"] - res["resolved_to"]) ** 2
    n_sel = res["target"].nunique()
    ok = res[~res["imputed"]]
    rank = pd.DataFrame({
        "brier": ok.groupby("model")["bs"].mean(),
        "n_scored": ok.groupby("model").size(),
        "imputed_share": res.groupby("model")["imputed"].sum() / n_sel,
    }).sort_values("brier")
    rank["eligible"] = rank["imputed_share"] <= C.IMPUTED_ELIGIBILITY_MAX
    elig = rank[rank["eligible"]]
    return rank, elig.index[0], n_sel


def target_level_model_stats(models):
    """Per-target model aggregates, imputed rows excluded (Amendment 1 A.3).

    DIS (Amendment 1 C.1): SD across the 17 base models within each scaffold
    separately, averaged over the two scaffolds.
    DIS_all34: SD across all 34 variants, diagnostic only.
    """
    ok = models[~models["imputed"]]
    per_scaffold = (ok.groupby(["target", "scaffold"])["p"]
                      .agg(sd=lambda s: s.std(ddof=C.SD_DDOF), n="size")
                      .reset_index())
    dis = (per_scaffold.groupby("target")["sd"].mean().rename("DIS"))
    n_sc = per_scaffold.pivot(index="target", columns="scaffold", values="n")
    all34 = ok.groupby("target")["p"].agg(
        DIS_all34=lambda s: s.std(ddof=C.SD_DDOF), n_models_used="size")
    p_b = ok.groupby("target")["p"].median().rename("p_b")
    out = pd.concat([dis, all34, p_b], axis=1)
    out = out.join(n_sc.add_prefix("n_"))
    return out.reset_index()


# --------------------------------------------------------- analysis frame
def build_frame(humans, models, stats, baseline_a):
    """One row per forecaster x target (SPEC §3), pilot filter applied later."""
    ba = models[models["model"] == baseline_a][
        ["target", "p", "imputed", "resolved_to"]].rename(
        columns={"p": "p_a", "imputed": "p_a_imputed"})
    df = humans.merge(ba, on="target", how="left", validate="many_to_one")
    df = df.merge(stats, on="target", how="left", validate="many_to_one")

    n_missing = int(df["p_a"].isna().sum())
    n_imp = int(df["p_a_imputed"].fillna(False).sum())
    df = df[df["p_a"].notna() & ~df["p_a_imputed"].fillna(False)].copy()

    # outcome consistency check between the two sources
    assert (df["o"] == df["resolved_to"]).all(), "outcome mismatch human vs model rows"

    df["BS_h"] = (df["p_h"] - df["o"]) ** 2
    df["BS_a"] = (df["p_a"] - df["o"]) ** 2
    df["BS_b"] = (df["p_b"] - df["o"]) ** 2
    df["G_a"] = df["BS_a"] - df["BS_h"]
    df["G_b"] = df["BS_b"] - df["BS_h"]
    df["D_a"] = df["p_h"] - df["p_a"]
    df["absD_a"] = df["D_a"].abs()
    df["D_b"] = df["p_h"] - df["p_b"]
    df["absD_b"] = df["D_b"].abs()
    df["CONF_a"] = (df["p_a"] - 0.5).abs()
    df["CONF_b"] = (df["p_b"] - 0.5).abs()
    df["EXT_a"] = (df["p_h"] - 0.5).abs() - df["CONF_a"]
    df["EXT_b"] = (df["p_h"] - 0.5).abs() - df["CONF_b"]
    # SPEC 9.5 blind spot: human and model on opposite sides of 0.5
    df["crossing"] = ((df["p_h"] - 0.5) * (df["p_a"] - 0.5)) < 0

    due = date.fromisoformat(C.DUE_DATE)
    df["HZ_days"] = [(date.fromisoformat(d) - due).days for d in df["res_date"]]
    df["logHZ"] = np.log(df["HZ_days"])          # Amendment 1 D.2
    df["MKT"] = df["source"].map(_is_market).astype(int)
    df["SRC"] = df["source"]                     # descriptive only (Amd 1 D.4)
    df["GRP"] = df["group"]

    # log score for robustness item 2 (SPEC 7.2)
    lo, hi = C.CLIP
    ph, pa = df["p_h"].clip(lo, hi), df["p_a"].clip(lo, hi)
    df["p_h_o"] = np.where(df["o"] == 1, ph, 1 - ph)
    df["p_a_o"] = np.where(df["o"] == 1, pa, 1 - pa)
    df["G_log"] = np.log(df["p_h_o"]) - np.log(df["p_a_o"])
    return df, dict(rows_missing_pa=n_missing, rows_dropped_pa_imputed=n_imp)


def pilot_questions(questions, fraction=C.PILOT_FRACTION, seed=C.PILOT_SEED):
    """Amendment 1 E.1: sample 30% of QUESTIONS, carry all their targets."""
    qs = sorted(questions)
    n = int(round(fraction * len(qs)))
    rng = np.random.default_rng(seed)
    return sorted(rng.choice(np.array(qs, dtype=object), size=n, replace=False).tolist()), n


def zscore(s):
    return (s - s.mean()) / s.std(ddof=0)
