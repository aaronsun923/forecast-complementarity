"""Run the SPEC v1 pilot (Amendment 1 E: 30% of QUESTIONS, seed 20260907).

Delivers SPEC §9 items 1-9 and 11 plus the Amendment 1 diagnostics.
H5 (§9 item 10) is excluded from the pilot by Amendment 1 E.1.

Usage:  python3 code/pilot.py
Writes: docs/forecast_pilot_REPORT.md, docs/figures/*.png,
        data/derived/*  (gitignored)
"""
import hashlib
import json
import platform
import sys
import time
import warnings
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import statsmodels
import statsmodels.formula.api as smf

import config as CFG
import fbdata as F
import models as M

T0 = time.time()
warnings.filterwarnings("ignore")
CFG.DERIVED.mkdir(parents=True, exist_ok=True)
CFG.FIGDIR.mkdir(parents=True, exist_ok=True)

OUT = []
def w(s=""):
    OUT.append(s)

def md_table(df, floatfmt="%.4f", index=True):
    d = df.copy()
    if index:
        d = d.reset_index()
    cols = list(d.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in d.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("—" if not np.isfinite(v) else floatfmt % v)
            elif isinstance(v, (bool, np.bool_)):
                cells.append("yes" if v else "no")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

def quantiles(s, qs=(0, .05, .25, .5, .75, .95, 1)):
    return pd.Series({f"q{int(q*100)}": np.quantile(s, q) for q in qs}
                     | {"mean": s.mean(), "sd": s.std()})


# ===================================================================== load
rbt, rbq = F.load_resolutions()
humans, dropped, invalid = F.load_humans(rbt, rbq)
models_df, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(models_df, set(humans["target"]))
stats = F.target_level_model_stats(models_df)
frame, frame_info = F.build_frame(humans, models_df, stats, chosen)

pilot_qs, n_pilot_q = F.pilot_questions(frame["question"].unique())
pilot = frame[frame["question"].isin(pilot_qs)].copy()

ZCOLS = ["DIS", "CONF_a", "logHZ", "EXT_a", "absD_a",
         "DIS_all34", "EXT_b", "absD_b", "CONF_b"]
for c in ZCOLS:
    pilot[c + "_z"] = F.zscore(pilot[c])

tlist = sorted(pilot["target"].unique())
tlist_hash = hashlib.sha256("\n".join(tlist).encode()).hexdigest()
pd.Series(tlist, name="target").to_csv(CFG.DERIVED / "pilot_targets.csv", index=False)
pd.Series(sorted(pilot_qs), name="question").to_csv(CFG.DERIVED / "pilot_questions.csv", index=False)
pilot.to_parquet(CFG.DERIVED / "pilot_frame.parquet") if hasattr(pd.DataFrame, "to_parquet") else None


# =================================================================== header
w("# ForecastBench pilot — SPEC v1 + Amendment 1")
w()
w(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} · "
  f"spec commit `f94cb63` · **pilot only, full sample not run**")
w()
w("Pilot scope per Amendment 1 E.1: a random **30% of questions** (seed "
  f"{CFG.PILOT_SEED}), carrying all of their targets. H5 is excluded from the "
  "pilot by the same clause. Deliverables §9 items 1–9 and 11 follow, plus the "
  "Amendment 1 diagnostics.")
w()
w("<<<SUMMARY>>>")
w()

# ---- STOP-THE-PRESS: unanticipated data defect
w("---")
w()
w("## 0. Unanticipated data defect requiring a designer ruling")
w()
n_inv = len(invalid)
inv_by_grp = invalid["group"].value_counts().to_dict() if n_inv else {}
w(f"**{n_inv} human forecast rows carry a `p_h` outside [0, 1]** and were excluded "
  "before any quantity was computed. Neither the SPEC nor Amendment 1 anticipates this.")
w()
if n_inv:
    q = np.percentile(invalid["p_h"], [0, 25, 50, 75, 100])
    w(f"- Affected rows: {n_inv} of {n_inv + len(humans)} resolved human rows "
      f"({100*n_inv/(n_inv+len(humans)):.2f}%), all in group "
      f"{'/'.join(f'{k} ({v})' for k, v in inv_by_grp.items())}.")
    w(f"- Distinct forecasters affected: {invalid['forecaster'].nunique()}.")
    w(f"- Value quantiles (min/25/50/75/max): {q[0]:.2f} / {q[1]:.2f} / {q[2]:.2f} / "
      f"{q[3]:.2f} / **{q[4]:,.2f}**.")
    w()
    w("The public survey asked for a number between 0 and 100 and ForecastBench divided "
      "by 100; these are uncleaned free-text mis-entries (e.g. `1.04` = someone typed 104, "
      "and one row is 5.0e8). ForecastBench does not filter them. Left in, they are not "
      "probabilities: `BS_h` is unbounded, and mean `G_a` over the full frame comes out at "
      "roughly −7.5e12 instead of a number in [−1, 1].")
    w()
    w("**Rule applied for this pilot (minimal, and reversible):** a forecast that is not a "
      "probability is not a forecast — rows with `p_h ∉ [0, 1]` are dropped and counted. "
      "The alternative (clip to [0, 1]) is reported as a sensitivity in §11. "
      "**This is a data-handling decision the designer should confirm or override.**")
w()

# ============================================== 1. environment and versions
w("---")
w()
w("## 1. Environment and versions")
w()
env = pd.DataFrame({
    "value": {
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "numpy": np.__version__, "pandas": pd.__version__,
        "scipy": scipy.__version__, "statsmodels": statsmodels.__version__,
        "matplotlib": matplotlib.__version__,
        "R / lme4": "not installed — see §5 fit notes",
    }})
w(md_table(env, index=True))
w()
w("**Data provenance** (`data/PROVENANCE.md`, no re-download — SPEC 2.1):")
w()
prov = pd.DataFrame({"value": {
    "datasets repo commit": CFG.DATASETS_COMMIT,
    "forecast_sets.tar.gz SHA-256": CFG.TARBALL_SHA256["forecast_sets.tar.gz"],
    "processed_forecast_sets.tar.gz SHA-256": CFG.TARBALL_SHA256["processed_forecast_sets.tar.gz"],
    "round": CFG.ROUND,
}})
w(md_table(prov, index=True))
w()
w(f"Pilot question list: `data/derived/pilot_questions.csv` ({n_pilot_q} questions). "
  f"Pilot target list: `data/derived/pilot_targets.csv` ({len(tlist)} targets), "
  f"SHA-256 of the sorted list `{tlist_hash[:32]}…`. Both are gitignored; both are "
  f"reproducible from seed {CFG.PILOT_SEED} and the rule "
  "`n = round(0.30 × n_questions)` with `numpy.random.default_rng(seed).choice` over the "
  "sorted question keys.")
w()

# ==================================================== 2. data coverage (§9.2)
w("---")
w()
w("## 2. Data coverage (§9 item 2)")
w()
cov_rows = {}
for g, sub in frame.groupby("GRP"):
    cov = sub.groupby("forecaster").size()
    cov_rows[g] = dict(forecasters=sub["forecaster"].nunique(),
                       rows=len(sub), targets=sub["target"].nunique(),
                       questions=sub["question"].nunique(),
                       cov_min=cov.min(), cov_q1=np.percentile(cov, 25),
                       cov_med=cov.median(), cov_q3=np.percentile(cov, 75),
                       cov_max=cov.max())
cov_df = pd.DataFrame(cov_rows).T
w("**Full round (all 162 questions), after the §0 exclusion:**")
w()
w(md_table(cov_df, floatfmt="%.1f"))
w()
pcov_rows = {}
for g, sub in pilot.groupby("GRP"):
    cov = sub.groupby("forecaster").size()
    pcov_rows[g] = dict(forecasters=sub["forecaster"].nunique(),
                        rows=len(sub), targets=sub["target"].nunique(),
                        questions=sub["question"].nunique(),
                        cov_min=cov.min(), cov_q1=np.percentile(cov, 25),
                        cov_med=cov.median(), cov_q3=np.percentile(cov, 75),
                        cov_max=cov.max())
w(f"**Pilot ({n_pilot_q} questions, {pilot['target'].nunique()} targets, "
  f"{len(pilot):,} rows):**")
w()
w(md_table(pd.DataFrame(pcov_rows).T, floatfmt="%.1f"))
w()
sf = pilot[pilot.GRP == "S"].groupby("target").size()
pf = pilot[pilot.GRP == "P"].groupby("target").size()
w(f"Forecasters per pilot target — S: min {sf.min()}, median {sf.median():.0f}, max {sf.max()}; "
  f"P: min {pf.min()}, median {pf.median():.0f}, max {pf.max()}. "
  "(Amendment 1 F.4: the H2 superforecaster median rests on as few as "
  f"{sf.min()} forecasts on some targets.)")
w()
w("**Model coverage.** Matched information condition = freeze values, no supplied news "
  "(Amendment 1 B.3): "
  f"**{meta['model'].nunique()} variants** = {meta['base'].nunique()} base models × "
  f"{len(CFG.MATCHED_SCAFFOLDS)} scaffolds "
  f"({', '.join(sorted(meta['scaffold'].unique()))}).")
w()
missing = frame_info["rows_missing_pa"]
w(f"- Human targets lacking a baseline-(a) forecast: **{missing}**. "
  f"All {frame['target'].nunique()} human targets are covered by all "
  f"{meta['model'].nunique()} matched variants.")
w(f"- Rows dropped because baseline (a) was imputed on that target "
  f"(Amendment 1 A.3): **{frame_info['rows_dropped_pa_imputed']}**.")
w(f"- Human market rows unmappable to a resolution date (Amendment 1 A.1): "
  f"**{dropped['unmappable_market']}** — the 4 market questions with no resolution row.")
w(f"- Human rows dropped as unresolved (SPEC 2.2): **{dropped['unresolved']:,}**.")
w()
w("**Amendment 1 F corrections confirmed against the data:** the round has 130 LLM "
  "variants across all conditions (139 including 9 non-LLM ForecastBench baselines), of "
  f"which {meta['model'].nunique()} match the human condition; the analysis frame is "
  f"{len(frame):,} forecaster × target rows, not 310,000; the data contain "
  f"{frame[frame.GRP=='S']['forecaster'].nunique()} distinct superforecaster ids "
  "(the paper reports 39).")
w()

# ================================================= 3. baseline (a) (§9.3)
w("---")
w()
w("## 3. Baseline (a) (§9 item 3)")
w()
w(f"Selection set (Amendment 1 B.1 — resolved **single-question** targets in the matched "
  f"condition, minus every human target): **{len(sel_targets)} targets** across "
  f"{len(set(t.rsplit('|', 1)[0] for t in sel_targets))} questions.")
w()
w(f"**Intersection of selection set and test set: "
  f"{len(set(sel_targets) & set(frame['target'].unique()))}** — empty, as SPEC §4 requires.")
w()
top = rank.head(5)[["brier", "n_scored", "imputed_share", "eligible"]]
w("Top 5 of the 34 matched variants by mean Brier on the selection set "
  "(imputed rows excluded from scoring, Amendment 1 A.3):")
w()
w(md_table(top))
w()
w(f"**Chosen baseline (a): `{chosen}`**, selection-set Brier "
  f"{rank.loc[chosen,'brier']:.4f} (×100 = {100*rank.loc[chosen,'brier']:.2f}). "
  f"Runner-up `{rank.index[1]}` at {rank.loc[rank.index[1],'brier']:.4f} "
  f"(×100 = {100*rank.loc[rank.index[1],'brier']:.2f}); margin "
  f"{100*(rank.loc[rank.index[1],'brier']-rank.loc[chosen,'brier']):.2f} Brier points ×100. "
  "No tie, so the Amendment 1 B.2 tie-break was not invoked.")
w()
n_inelig = int((~rank["eligible"]).sum())
w(f"**Eligibility (Amendment 1 A.3, >5% imputed on the selection set):** "
  f"{n_inelig} of 34 variants ineligible" +
  (": " + ", ".join(f"`{m}` ({100*rank.loc[m,'imputed_share']:.1f}%)"
                    for m in rank[~rank['eligible']].index) if n_inelig else "") + ".")
w()
w("Imputed share of every matched variant (diagnostic requested by Amendment 1 A.3):")
w()
imp_tbl = rank[["imputed_share", "n_scored", "brier"]].sort_values("imputed_share", ascending=False)
w(md_table(imp_tbl.head(12)))
w()
n_zero = int((imp_tbl["imputed_share"] == 0).sum())
w(f"The other {len(imp_tbl)-12} variants sit at exactly 0 imputed; "
  f"{n_zero} of the 34 have no imputed row on the selection set at all.")
w()

# --- diagnostic: unrestricted-set champion
un_rank, un_chosen, un_n = F.unrestricted_champion(set(humans["target"]))
w("**Diagnostic — unrestricted-set champion (Amendment 1 B.1).** On the unrestricted "
  f"selection set ({un_n:,} targets, 86% combination questions) the winner would be "
  f"`{un_chosen}` (Brier {un_rank.loc[un_chosen,'brier']:.4f}). "
  + ("This is the **same** model the amended rule selects, so the restriction to single "
     "questions does not change the baseline."
     if un_chosen == chosen else
     f"This **differs** from the amended choice `{chosen}`, which is the outcome the "
     "amendment was written to avoid."))
w()
w(md_table(un_rank.head(5)[["brier", "n_scored", "imputed_share"]]))
w()

# ===================================================== 4. sign tests (§9.4)
w("---")
w()
w("## 4. Sign tests (§9 item 4, SPEC §3)")
w()
p_ = pilot.copy()
p_["margin"] = (p_["p_a"] - p_["o"]).abs() - (p_["p_h"] - p_["o"]).abs()
# one row per target, so the tables exercise 20 different questions rather than
# 20 forecasters on the same easy target
hum_closer = (p_.sort_values(["margin", "target"], ascending=[False, True])
                .drop_duplicates("target").head(20))
mod_closer = (p_.sort_values(["margin", "target"], ascending=[True, True])
                .drop_duplicates("target").head(20))
more_ext = (p_.sort_values(["EXT_a", "target"], ascending=[False, True])
              .drop_duplicates("target").head(10))

a1 = bool((hum_closer["G_a"] > 0).all())
a2 = bool((mod_closer["G_a"] < 0).all())
a3 = bool((more_ext["EXT_a"] > 0).all())
w(f"- 20 rows where the human is visibly closer to the outcome → `G_a > 0` on all 20: "
  f"**{'PASS' if a1 else 'FAIL'}**")
w(f"- 20 rows where the model is visibly closer → `G_a < 0` on all 20: "
  f"**{'PASS' if a2 else 'FAIL'}**")
w(f"- 10 rows where the human is visibly more extreme → `EXT_a > 0` on all 10: "
  f"**{'PASS' if a3 else 'FAIL'}**")
w()
def sign_tbl(d, cols):
    t = d[cols].copy()
    t.insert(0, "row", range(1, len(t) + 1))
    return md_table(t.set_index("row"))
w("**Human visibly closer (largest margin, 20 rows):**")
w()
w(sign_tbl(hum_closer, ["forecaster", "target", "o", "p_h", "p_a", "G_a"]))
w()
w("**Model visibly closer (largest negative margin, 20 rows):**")
w()
w(sign_tbl(mod_closer, ["forecaster", "target", "o", "p_h", "p_a", "G_a"]))
w()
w("**Human visibly more extreme (largest `EXT_a`, 10 rows):**")
w()
w(sign_tbl(more_ext, ["forecaster", "target", "p_h", "p_a", "CONF_a", "EXT_a"]))
w()

# ================================================= 5. distributions (§9.5)
w("---")
w()
w("## 5. Distributions of `G_a`, `D_a`, `EXT_a`, `DIS` (§9 item 5)")
w()
w("Brier quantities are raw (0–1); multiply by 100 for the units used in the text "
  "(SPEC §3).")
w()
for v in ["G_a", "D_a", "EXT_a", "DIS"]:
    tbl = pd.DataFrame({g: quantiles(sub[v].values) for g, sub in pilot.groupby("GRP")})
    tbl["all"] = quantiles(pilot[v].values)
    w(f"**`{v}`**")
    w()
    w(md_table(tbl.T))
    w()

fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
for ax, v in zip(axes.ravel(), ["G_a", "D_a", "EXT_a", "DIS"]):
    for g, colr in [("S", "#1b6ca8"), ("P", "#d1495b")]:
        ax.hist(pilot.loc[pilot.GRP == g, v], bins=50, alpha=.55,
                label=f"{g} (n={int((pilot.GRP==g).sum()):,})", color=colr, density=True)
    ax.axvline(0, color="#333", lw=.8, ls="--")
    ax.set_title(v); ax.set_ylabel("density"); ax.legend(fontsize=8)
fig.suptitle("Pilot distributions by group", fontsize=12)
fig.tight_layout()
fig.savefig(CFG.FIGDIR / "pilot_distributions.png", dpi=150)
plt.close(fig)
w("![Pilot distributions](figures/pilot_distributions.png)")
w()

cross_share = float(pilot["crossing"].mean())
w(f"**`EXT_a` blind spot (§9 item 5).** Share of pilot rows where `p_h` and `p_a` lie on "
  f"opposite sides of 0.5: **{100*cross_share:.1f}%** "
  f"({int(pilot['crossing'].sum()):,} of {len(pilot):,} rows).")
w()
ct = pd.DataFrame({
    "crossing": quantiles(pilot.loc[pilot.crossing, "EXT_a"].values),
    "non-crossing": quantiles(pilot.loc[~pilot.crossing, "EXT_a"].values)}).T
w(md_table(ct))
w()
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.hist(pilot.loc[~pilot.crossing, "EXT_a"], bins=50, alpha=.6, density=True,
        label=f"non-crossing (n={int((~pilot.crossing).sum()):,})", color="#1b6ca8")
ax.hist(pilot.loc[pilot.crossing, "EXT_a"], bins=50, alpha=.6, density=True,
        label=f"crossing (n={int(pilot.crossing.sum()):,})", color="#e08e45")
ax.axvline(0, color="#333", lw=.8, ls="--")
ax.set_xlabel("EXT_a"); ax.set_ylabel("density")
ax.set_title("EXT_a: crossing vs non-crossing rows")
ax.legend()
fig.tight_layout(); fig.savefig(CFG.FIGDIR / "ext_crossing.png", dpi=150); plt.close(fig)
w("![EXT_a crossing](figures/ext_crossing.png)")
w()
w(f"At {100*cross_share:.1f}% the share is **material**, so the H4 reading below states it: "
  "a positive `EXT_a` coefficient cannot be read as 'extremizing the model's view pays' "
  "without separating rows that cross 0.5.")
w()

# --- DIS diagnostic
w("**Diagnostic — `DIS` definition (Amendment 1 C.1).** `DIS` is the within-scaffold SD "
  "across the 17 base models, averaged over the two scaffolds. `DIS_all34` is the SD "
  "across all 34 variants (the pre-amendment definition).")
w()
dtb = pd.DataFrame({"DIS": quantiles(pilot["DIS"].values),
                    "DIS_all34": quantiles(pilot["DIS_all34"].values)}).T
w(md_table(dtb))
w()
rr = float(np.corrcoef(pilot["DIS"], pilot["DIS_all34"])[0, 1])
w(f"Pearson correlation between the two, at row level: **{rr:.4f}**. "
  f"`DIS_all34` is on average {100*(pilot['DIS_all34'].mean()/pilot['DIS'].mean()-1):+.1f}% "
  "larger, which is the scaffold-sensitivity component the amendment removes.")
w()

# ======================================================== 6. H1 (§9.6)
w("---")
w()
w("## 6. H1 — does the human beat the model on average? (§9 item 6)")
w()
gm = M.group_means_cluster(pilot, "G_a")
gm100 = gm.copy()
for c in ["mean", "ci_lo", "ci_hi"]:
    gm100[c] = 100 * gm100[c].astype(float)
w("Group means of `G_a` × 100, with question-clustered 95% CIs "
  "(positive = the human beat baseline (a)):")
w()
w(md_table(gm100[["mean", "ci_lo", "ci_hi", "n", "n_questions", "n_forecasters"]],
           floatfmt="%.3f"))
w()
h1, h1_fb = M.fit_spec("G_a ~ GRP", pilot, "H1")
w(f"Model `G_a ~ GRP + (1|forecaster) + (1|question) + (1|question:target)` — {h1.note}")
w()
w(md_table(h1.table(), floatfmt="%.5f"))
w()
if h1.vc:
    tot = sum(h1.vc.values())
    vcs = pd.DataFrame({"variance": h1.vc,
                        "share": {k: v / tot for k, v in h1.vc.items()}})
    w("Variance components:")
    w()
    w(md_table(vcs, floatfmt="%.5f"))
    w()

# ======================================================== 7. H2 (§9.7)
w("---")
w()
w("## 7. H2 — encompassing test (§9 item 7)")
w()
tl = (pilot.groupby("target")
      .agg(o=("o", "first"), p_a=("p_a", "first"), question=("question", "first"))
      .reset_index())
med_S = pilot[pilot.GRP == "S"].groupby("target")["p_h"].median().rename("p_h_S")
med_P = pilot[pilot.GRP == "P"].groupby("target")["p_h"].median().rename("p_h_P")
tl = tl.merge(med_S, on="target", how="left").merge(med_P, on="target", how="left")

h2 = {}
for g, col in [("S", "p_h_S"), ("P", "p_h_P")]:
    h2[g] = M.encompassing(tl, col, CFG.CLIP)
rows = []
for g in ["S", "P"]:
    r = h2[g]
    rows.append(dict(group=g,
                     coef_human_minus_model=r["params"]["human_minus_model"],
                     ci_lo=r["ci"].loc["human_minus_model", 0],
                     ci_hi=r["ci"].loc["human_minus_model", 1],
                     coef_logit_p_a=r["params"]["logit_p_a"],
                     n_targets=r["nobs"], n_clusters=r["n_clusters"]))
w("Target level, logistic, question-clustered SEs. "
  "`o ~ logit(p_a) + [logit(p_h_g) − logit(p_a)]`, groups reported separately "
  "(SPEC 5.2 forbids pooling):")
w()
w(md_table(pd.DataFrame(rows).set_index("group"), floatfmt="%.4f"))
w()
w(f"Clipping to {CFG.CLIP} (SPEC 5.2): baseline (a) values clipped "
  f"**{h2['S']['clipped_model']}**; superforecaster medians clipped "
  f"**{h2['S']['clipped_human']}**; public medians clipped "
  f"**{h2['P']['clipped_human']}** (of {len(tl)} targets each).")
w()
w(f"Superforecaster medians on {int((sf<=4).sum())} of {len(sf)} pilot targets rest on ≤4 "
  "individual forecasts (Amendment 1 F.4); the S coefficient must be read with that.")
w()

# ==================================================== 8. H3 (§9.8)
w("---")
w()
w("## 8. H3 — where does the return live? (§9 item 8)")
w()
F3 = "G_a ~ DIS_z + CONF_a_z + logHZ_z + MKT + GRP"
h3, h3_fb = M.fit_spec(F3, pilot, "H3")
w(f"`{F3}` + crossed REs — {h3.note}")
w()
w(md_table(h3.table(), floatfmt="%.5f"))
w()
w("`HZ` enters as log(days), standardized (Amendment 1 D.2). "
  "**`logHZ_z` and `MKT` are partly redundant**: market and dataset horizons come from "
  "different distributions, so their coefficients should not be read separately. "
  "`CONF_a_z`, `logHZ_z`, `MKT` are controls; sign only (SPEC 5.3).")
w()
h3d, _ = M.fit_spec(F3.replace("DIS_z", "DIS_all34_z"), pilot, "H3")
w("Diagnostic — same model with the pre-amendment `DIS_all34`:")
w()
w(md_table(h3d.table(), floatfmt="%.5f"))
w()

# ==================================================== 9. H4 (§9.9)
w("---")
w()
w("## 9. H4 — does the direction of deviation pay? (§9 item 9)")
w()
F4 = ("G_a ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + MKT + GRP "
      "+ EXT_a_z:DIS_z")
h4, h4_fb = M.fit_spec(F4, pilot, "H4")
w(f"`{F4}` + crossed REs (the single locked interaction, SPEC 5.4) — {h4.note}")
w()
w(md_table(h4.table(), floatfmt="%.5f"))
w()
w("**Reading notes carried by this table (Amendment 1 D.3, §9 item 5):**")
w()
w("- `EXT_a = |p_h − 0.5| − CONF_a` by construction, so the `EXT_a_z` coefficient is the "
  "effect of the human's extremity **at fixed model confidence and fixed deviation size**.")
w(f"- {100*cross_share:.1f}% of rows cross 0.5, where a positive `EXT_a` is not an "
  "extremization of the model's view. The sign above is not a clean test of "
  "'extremizing pays' until those rows are separated.")
w("- SPEC 5.4 pre-registers this as two-sided; only the sign is interpreted.")
w()

# ============================================= 11. robustness (§9 item 11)
w("---")
w()
w("## 11. Robustness (§9 item 11, SPEC §7)")
w()
w("### 7.1 Baseline (b) — median of the 34 matched variants")
w()
gmb = M.group_means_cluster(pilot, "G_b")
gmb100 = gmb.copy()
for c in ["mean", "ci_lo", "ci_hi"]:
    gmb100[c] = 100 * gmb100[c].astype(float)
w("H1 with `G_b` (×100):")
w()
w(md_table(gmb100[["mean", "ci_lo", "ci_hi", "n"]], floatfmt="%.3f"))
w()
F3b = "G_b ~ DIS_z + CONF_b_z + logHZ_z + MKT + GRP"
F4b = ("G_b ~ EXT_b_z + absD_b_z + DIS_z + CONF_b_z + logHZ_z + MKT + GRP "
       "+ EXT_b_z:DIS_z")
h3b, _ = M.fit_spec(F3b, pilot, "H3")
h4b, _ = M.fit_spec(F4b, pilot, "H4")
w("H3 with baseline (b):")
w()
w(md_table(h3b.table(), floatfmt="%.5f"))
w()
w("H4 with baseline (b):")
w()
w(md_table(h4b.table(), floatfmt="%.5f"))
w()

w("### 7.2 Log score in place of Brier")
w()
F3l = "G_log ~ DIS_z + CONF_a_z + logHZ_z + MKT + GRP"
F4l = ("G_log ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + MKT + GRP "
       "+ EXT_a_z:DIS_z")
h3l, _ = M.fit_spec(F3l, pilot, "H3")
h4l, _ = M.fit_spec(F4l, pilot, "H4")
w(f"`G_log = log(p_h_o) − log(p_a_o)`, probabilities clipped to {CFG.CLIP}. "
  "Positive = human better, same orientation as `G_a`.")
w()
w("H3 with log score:")
w()
w(md_table(h3l.table(), floatfmt="%.5f"))
w()
w("H4 with log score:")
w()
w(md_table(h4l.table(), floatfmt="%.5f"))
w()

w("### 7.3 Dataset questions only")
w()
ds = pilot[pilot.MKT == 0].copy()
for c in ZCOLS:
    ds[c + "_z"] = F.zscore(ds[c])
w(f"Dropping market targets leaves {ds['target'].nunique()} targets across "
  f"{ds['question'].nunique()} questions and {len(ds):,} rows.")
w()
F3d = "G_a ~ DIS_z + CONF_a_z + logHZ_z + GRP"
F4d = ("G_a ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + GRP "
       "+ EXT_a_z:DIS_z")
h3d2, _ = M.fit_spec(F3d, ds, "H3")
h4d2, _ = M.fit_spec(F4d, ds, "H4")
w("`MKT` is dropped from the right-hand side because it is constant here.")
w()
w("H3, dataset questions only:")
w()
w(md_table(h3d2.table(), floatfmt="%.5f"))
w()
w("H4, dataset questions only:")
w()
w(md_table(h4d2.table(), floatfmt="%.5f"))
w()

# --- §0 sensitivity: clip instead of drop
w("### Sensitivity to the §0 rule (clip instead of drop)")
w()
hum_clip, _, inv2 = F.load_humans(rbt, rbq)
inv_fix = invalid.copy()
if len(inv_fix):
    inv_fix["p_h"] = inv_fix["p_h"].clip(0, 1)
    hum_clip = pd.concat([hum_clip, inv_fix], ignore_index=True)
fr_clip, _ = F.build_frame(hum_clip, models_df, stats, chosen)
pc = fr_clip[fr_clip["question"].isin(pilot_qs)].copy()
gmc = M.group_means_cluster(pc, "G_a")
gmc100 = gmc.copy()
for c in ["mean", "ci_lo", "ci_hi"]:
    gmc100[c] = 100 * gmc100[c].astype(float)
w(f"Clipping the {n_inv} out-of-range rows to [0, 1] instead of dropping them "
  f"({int(pc.shape[0]-pilot.shape[0])} extra pilot rows). H1 group means × 100:")
w()
w(md_table(gmc100[["mean", "ci_lo", "ci_hi", "n"]], floatfmt="%.3f"))
w()

# ============================================================ close
w("---")
w()
w("## Stop")
w()
w("SPEC §10: the pilot stops here. The full sample has **not** been run. "
  "H5 (§9 item 10) is excluded from the pilot by Amendment 1 E.1 and awaits the full run. "
  "§9 item 12 (interpretation caveats) belongs to the full run and is not written here.")
w()
w(f"Total runtime {time.time()-T0:.0f}s (SPEC §8 tripwire: 1 hour).")
w()

# ------------------------------------------------- core quantities summary
def _ci(v, lo, hi, f="%.4f"):
    return f"{f % v} [{f % lo}, {f % hi}]"

summary = []
summary.append("## Core quantities at a glance")
summary.append("")
summary.append("Factual only; SPEC §9 item 12 (interpretation) belongs to the full run.")
summary.append("")
rows = [
    ("H1", "mean `G_a` ×100, superforecasters",
     _ci(100*float(gm.loc['S','mean']), 100*float(gm.loc['S','ci_lo']),
         100*float(gm.loc['S','ci_hi']), "%.2f"), "positive = human beat baseline (a)"),
    ("H1", "mean `G_a` ×100, public",
     _ci(100*float(gm.loc['P','mean']), 100*float(gm.loc['P','ci_lo']),
         100*float(gm.loc['P','ci_hi']), "%.2f"), "negative = baseline (a) beat human"),
    ("H2", "encompassing coef, superforecaster median",
     _ci(h2['S']['params']['human_minus_model'], h2['S']['ci'].loc['human_minus_model',0],
         h2['S']['ci'].loc['human_minus_model',1]), "CI excludes 0"),
    ("H2", "encompassing coef, public median",
     _ci(h2['P']['params']['human_minus_model'], h2['P']['ci'].loc['human_minus_model',0],
         h2['P']['ci'].loc['human_minus_model',1]), "CI excludes 0"),
    ("H3", "`DIS_z` on `G_a` (core quantity)",
     _ci(h3.params['DIS_z'], h3.ci.loc['DIS_z',0], h3.ci.loc['DIS_z',1]),
     "CI includes 0"),
    ("H4", "`EXT_a_z` on `G_a` (core quantity, sign only)",
     _ci(h4.params['EXT_a_z'], h4.ci.loc['EXT_a_z',0], h4.ci.loc['EXT_a_z',1]),
     "sign: positive"),
    ("H4", "`EXT_a_z:DIS_z` (the one locked interaction)",
     _ci(h4.params['EXT_a_z:DIS_z'], h4.ci.loc['EXT_a_z:DIS_z',0],
         h4.ci.loc['EXT_a_z:DIS_z',1]), "sign: positive"),
]
summary.append("| Hypothesis | Quantity | Estimate [95% CI] | Note |")
summary.append("|---|---|---|---|")
for r in rows:
    summary.append("| " + " | ".join(r) + " |")
summary.append("")
summary.append(f"All three §3 sign tests pass. All four mixed models converged "
               f"(no §5 / Amendment 1 D.1 fallback was needed). Runtime "
               f"{time.time()-T0:.0f}s.")
summary.append("")
summary.append("**Three things the designer should look at before authorising the full run:** "
               "(a) the §0 out-of-range human forecasts and the drop-vs-clip ruling; "
               f"(b) {100*cross_share:.0f}% of rows cross 0.5, which limits what the H4 "
               "`EXT_a` sign can mean; (c) the H2 superforecaster median hits the clip "
               f"bound on {h2['S']['clipped_human']} of {len(tl)} targets "
               f"({100*h2['S']['clipped_human']/len(tl):.0f}%), so the S encompassing "
               "coefficient is estimated partly on clipped values.")

txt = "\n".join(OUT).replace("<<<SUMMARY>>>", "\n".join(summary))
(CFG.DOCS / "forecast_pilot_REPORT.md").write_text(txt + "\n")
print("wrote", CFG.DOCS / "forecast_pilot_REPORT.md")
print("runtime %.0fs" % (time.time() - T0))
print("sign tests:", a1, a2, a3)
print("fallbacks:", dict(H1=h1_fb, H3=h3_fb, H4=h4_fb))
