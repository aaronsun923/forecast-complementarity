"""SPEC v1 Amendment 4: H5 with a question-level split.

The locked H5 path in full.py is not touched. This reads the full-run frame
that full.py wrote (data/derived/full_frame.pkl), recomputes the locked
target-level split as a check against the report, then runs the Amendment 4
question-level split.

Usage:  python3 code/amendment4_h5.py
Writes: docs/figures/full_h5_question_split.png, and appends (or replaces) the
        section "Amendment 4: H5 question-level split" in
        docs/forecast_full_REPORT.md.
"""
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats

import config as CFG
from report import md_table

HEADING = "## Amendment 4: H5 question-level split"
N_SPLITS = 1000             # Amendment 4: seeds 1..1000, descriptive only
LOCKED_R = {"S": 0.7818, "P": 0.6400}   # docs/forecast_full_REPORT.md §10


def loo_demean(full):
    """SPEC 5.5 + Amendment 1 D.5: leave-one-out, pooled across groups."""
    g = full.groupby("target")["G_a"]
    tsum, tn = g.transform("sum"), g.transform("size")
    assert (tn >= 2).all(), "a target has a single forecaster; LOO undefined"
    return full["G_a"] - (tsum - full["G_a"]) / (tn - 1)


def half_means(full, unit, seed):
    """Assign sorted `unit` values to halves by one permutation; per-forecaster
    half means of G_dm. Returns (means incl. NaN for an empty half, n per half)."""
    rng = np.random.default_rng(seed)
    units = np.array(sorted(full[unit].unique()), dtype=object)
    perm = rng.permutation(len(units))
    half_a = set(units[perm[:len(units) // 2]])
    half = np.where(full[unit].isin(half_a), "A", "B")
    key = [full["GRP"], full["forecaster"], half]
    hm = full.groupby(key)["G_dm"].mean().unstack(-1)
    cnt = full.groupby(key).size().unstack(-1).fillna(0).astype(int)
    hm.index.names = cnt.index.names = ["GRP", "forecaster"]
    return hm, cnt, len(half_a), len(units) - len(half_a)


def boot_corr(x, y, draws=CFG.BOOTSTRAP_DRAWS, seed=CFG.SPLIT_HALF_SEED):
    """Same percentile bootstrap as full.py (resample forecasters)."""
    r = np.random.default_rng(seed)
    n = len(x)
    out = np.empty(draws)
    for i in range(draws):
        idx = r.integers(0, n, n)
        xa, ya = x[idx], y[idx]
        out[i] = np.nan if xa.std() == 0 or ya.std() == 0 else np.corrcoef(xa, ya)[0, 1]
    return np.nanpercentile(out, [2.5, 97.5])


def pearson(sub):
    return float(np.corrcoef(sub["A"].values, sub["B"].values)[0, 1])


def main():
    full = pd.read_pickle(CFG.DERIVED / "full_frame.pkl")
    full["G_dm"] = loo_demean(full)
    n_fc = full.groupby("GRP")["forecaster"].nunique()

    # --- check: the locked target-level split reproduces the report ----
    hm_t, _, _, _ = half_means(full, "target", CFG.SPLIT_HALF_SEED)
    hm_t = hm_t.dropna()
    old = {g: pearson(hm_t.loc[g]) for g in ["S", "P"]}
    for g in ["S", "P"]:
        assert round(old[g], 4) == LOCKED_R[g], (g, old[g])

    # --- primary: question-level split, seed 20260906 ------------------
    hm_q, cnt_q, nA, nB = half_means(full, "question", CFG.SPLIT_HALF_SEED)
    rows = []
    for g in ["S", "P"]:
        sub = hm_q.loc[g].dropna()
        c = cnt_q.loc[g].loc[sub.index]
        x, y = sub["A"].values, sub["B"].values
        lo, hi = boot_corr(x, y)
        rows.append(dict(group=g, n_included=len(sub),
                         n_excluded=int(n_fc[g] - len(sub)),
                         pearson_r=pearson(sub), ci_lo=lo, ci_hi=hi,
                         spearman_r=float(scipy.stats.spearmanr(x, y).statistic),
                         min_targets_in_smaller_half=int(c.min(axis=1).min()),
                         target_level_r_locked=old[g]))
    prim = pd.DataFrame(rows).set_index("group")

    # --- descriptive: 1,000 question-level splits, seeds 1..1000 -------
    dist = {g: np.empty(N_SPLITS) for g in ["S", "P"]}
    excl = {g: np.empty(N_SPLITS, dtype=int) for g in ["S", "P"]}
    for i, seed in enumerate(range(1, N_SPLITS + 1)):
        hm, _, _, _ = half_means(full, "question", seed)
        for g in ["S", "P"]:
            sub = hm.loc[g].dropna()
            dist[g][i] = pearson(sub)
            excl[g][i] = n_fc[g] - len(sub)
    drows = []
    for g in ["S", "P"]:
        d = dist[g]
        drows.append(dict(group=g, median=np.median(d),
                          p2_5=np.percentile(d, 2.5), p97_5=np.percentile(d, 97.5),
                          min=d.min(), max=d.max(),
                          share_below_locked_target_r=float((d < old[g]).mean()),
                          max_excluded=int(excl[g].max())))
    dtab = pd.DataFrame(drows).set_index("group")

    # --- figure: same layout as full_h5_splithalf.png -----------------
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    for ax, g, colr in zip(axes, ["S", "P"], ["#1b6ca8", "#d1495b"]):
        sub = hm_q.loc[g].dropna()
        ax.scatter(sub["A"], sub["B"], s=18, alpha=.65, color=colr, edgecolor="none")
        ax.axhline(0, color="#999", lw=.7); ax.axvline(0, color="#999", lw=.7)
        ax.set_title(f"{g}: r = {prim.loc[g, 'pearson_r']:.3f}  (n = {len(sub)})")
        ax.set_xlabel("half A mean of demeaned G_a"); ax.set_ylabel("half B mean")
    fig.suptitle("H5 split-half stability of the human's return, question-level split "
                 "(Amendment 4)", fontsize=12)
    fig.tight_layout()
    fig.savefig(CFG.FIGDIR / "full_h5_question_split.png", dpi=150)
    plt.close(fig)

    # --- report section ------------------------------------------------
    L = [HEADING, "",
         "Specified after the results were seen (SPEC v1 Amendment 4, commit `c4063e1`). "
         "The locked H5 split in §10 assigned targets to halves. Targets of one question at "
         "different horizons often share an outcome and a forecaster's judgment, so that "
         "split can place one judgment in both halves. Here every target of a question goes "
         "to the same half. Leave-one-out demeaning (pooled, Amendment 1 D.5), the 2,000-draw "
         "forecaster bootstrap and its seed are unchanged. The target-level result in §10 "
         "remains the originally locked estimate.", "",
         f"Check: the locked target-level split recomputed from the stored frame gives "
         f"S {old['S']:.4f}, P {old['P']:.4f}, matching §10.", "",
         f"**Primary.** One random assignment of the {nA + nB} questions, seed "
         f"{CFG.SPLIT_HALF_SEED} ({nA} questions in half A, {nB} in half B). A forecaster "
         "enters only with at least one target in each half.", "",
         md_table(prim, floatfmt="%.4f"), "",
         f"**Split dependence (descriptive only).** Pearson r over {N_SPLITS:,} question-level "
         "splits, seeds 1 to 1,000. `share_below_locked_target_r` is the share of splits "
         "whose r falls below the locked target-level r for that group; `max_excluded` is the "
         "largest number of forecasters excluded in any split.", "",
         md_table(dtab, floatfmt="%.4f"), "",
         "![H5 question-level split](figures/full_h5_question_split.png)", ""]
    section = "\n".join(L)

    rp = CFG.DOCS / "forecast_full_REPORT.md"
    text = rp.read_text()
    if HEADING in text:
        text = re.sub(re.escape(HEADING) + r".*?(?=\n## |\Z)", section.rstrip("\n") + "\n",
                      text, flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n---\n\n" + section
    rp.write_text(text)

    print(prim.to_string()); print(); print(dtab.to_string())


if __name__ == "__main__":
    sys.exit(main())
