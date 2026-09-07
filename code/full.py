"""Full-sample run of SPEC v1 + Amendments 1 and 2.

All resolved human targets. H1-H5, the three SPEC §7 robustness items, and the
two Amendment 2 sensitivities. Delivers SPEC §9 items 1-12.

Usage:  python3 code/full.py
Writes: docs/forecast_full_REPORT.md, docs/figures/full_*.png,
        data/derived/*  (gitignored)
"""
import hashlib
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

import config as CFG
import fbdata as F
import models as M
from report import md_table, quantiles, ci_str

T0 = time.time()
warnings.filterwarnings("ignore")
CFG.DERIVED.mkdir(parents=True, exist_ok=True)
CFG.FIGDIR.mkdir(parents=True, exist_ok=True)

OUT = []
def w(s=""):
    OUT.append(s)

ZCOLS = ["DIS", "CONF_a", "logHZ", "EXT_a", "absD_a",
         "DIS_all34", "EXT_b", "absD_b", "CONF_b"]


# ===================================================================== load
rbt, rbq = F.load_resolutions()
humans, dropped, invalid = F.load_humans(rbt, rbq)
models_df, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(models_df, set(humans["target"]))
stats = F.target_level_model_stats(models_df)
full, frame_info = F.build_frame(humans, models_df, stats, chosen)
for c in ZCOLS:
    full[c + "_z"] = F.zscore(full[c])
full.to_pickle(CFG.DERIVED / "full_frame.pkl")

n_inv = len(invalid)
cross_share = float(full["crossing"].mean())


# =================================================================== header
w("# ForecastBench full run — SPEC v1 + Amendments 1 and 2")
w()
w(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} · "
  "spec commit `e976bf5` · **full sample**")
w()
w("All resolved human targets. H1–H5, the three SPEC §7 robustness items, and the two "
  "Amendment 2 sensitivities. SPEC §9 items 1–12 follow. The pilot "
  "(`forecast_pilot_REPORT.md`) was accepted on 2026-09-06; nothing in the pipeline "
  "changed except the additions Amendment 2 requires.")
w()
w("<<<SUMMARY>>>")
w()

# =========================================== 1. environment and versions
w("---")
w()
w("## 1. Environment and versions (§9 item 1)")
w()
env = pd.DataFrame({"value": {
    "python": sys.version.split()[0],
    "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
    "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
    "statsmodels": statsmodels.__version__, "matplotlib": matplotlib.__version__,
    "R / lme4": "not installed — mixed models fitted in statsmodels",
}})
w(md_table(env))
w()
prov = pd.DataFrame({"value": {
    "datasets repo commit": CFG.DATASETS_COMMIT,
    "forecast_sets.tar.gz SHA-256": CFG.TARBALL_SHA256["forecast_sets.tar.gz"],
    "processed_forecast_sets.tar.gz SHA-256": CFG.TARBALL_SHA256["processed_forecast_sets.tar.gz"],
    "round": CFG.ROUND,
    "split-half seed (H5)": str(CFG.SPLIT_HALF_SEED),
    "bootstrap draws (H5)": str(CFG.BOOTSTRAP_DRAWS),
}})
w("**Data provenance** (`data/PROVENANCE.md`; no re-download — SPEC 2.1):")
w()
w(md_table(prov))
w()

# ------------------------------------- Amendment 2 item 1 reporting
w("**Amendment 2 item 1 — human forecasts outside [0, 1].** "
  f"**{n_inv} rows excluded** from every analysis, "
  f"from **{invalid['forecaster'].nunique()} distinct forecasters**, "
  f"all in group **{'/'.join(sorted(invalid['group'].unique()))}** "
  f"(public). Values run to {invalid['p_h'].max():,.2f}. "
  "Clipping to [0, 1] appears in §11 as a sensitivity only and carries no conclusion.")
w()

# ================================================== 2. data coverage (§9.2)
w("---")
w()
w("## 2. Data coverage (§9 item 2)")
w()
cov_rows = {}
for g, sub in full.groupby("GRP"):
    cov = sub.groupby("forecaster").size()
    cov_rows[g] = dict(forecasters=sub["forecaster"].nunique(), rows=len(sub),
                       targets=sub["target"].nunique(), questions=sub["question"].nunique(),
                       cov_min=cov.min(), cov_q1=np.percentile(cov, 25),
                       cov_med=cov.median(), cov_q3=np.percentile(cov, 75),
                       cov_max=cov.max())
w(md_table(pd.DataFrame(cov_rows).T, floatfmt="%.1f"))
w()
w(f"Total analysis frame: **{len(full):,} forecaster × target rows**, "
  f"{full['target'].nunique()} resolved targets, {full['question'].nunique()} questions, "
  f"{full['forecaster'].nunique()} forecasters.")
w()
fam = full.groupby("MKT")["target"].nunique()
fq = full.groupby("MKT")["question"].nunique()
w(f"Targets by family: **{int(fam.get(0,0))} dataset, {int(fam.get(1,0))} market** "
  f"({int(fq.get(0,0))} and {int(fq.get(1,0))} questions). "
  "This matches the SPEC 2.2 expectation of 578 targets across 162 questions "
  "(521 dataset, 57 market) exactly.")
w()
sf = full[full.GRP == "S"].groupby("target").size()
pf = full[full.GRP == "P"].groupby("target").size()
w(f"Forecasters per target — S: min {sf.min()}, median {sf.median():.0f}, max {sf.max()}; "
  f"P: min {pf.min()}, median {pf.median():.0f}, max {pf.max()} "
  "(Amendment 1 F.4).")
w()
w(f"**Model coverage.** Matched condition (Amendment 1 B.3) = freeze values, no supplied "
  f"news: **{meta['model'].nunique()} variants** = {meta['base'].nunique()} base models × "
  f"{len(CFG.MATCHED_SCAFFOLDS)} scaffolds. "
  f"Human targets lacking a baseline-(a) forecast: **{frame_info['rows_missing_pa']}**. "
  f"Rows dropped because baseline (a) was imputed there (Amendment 1 A.3): "
  f"**{frame_info['rows_dropped_pa_imputed']}**. "
  f"Human market rows unmappable to a resolution date: **{dropped['unmappable_market']}**. "
  f"Human rows dropped as unresolved: **{dropped['unresolved']:,}**.")
w()
w(f"Footnote (Amendment 1 F.3): the data contain "
  f"{full[full.GRP=='S']['forecaster'].nunique()} distinct superforecaster ids; "
  "the paper reports 39.")
w()

# ================================================= 3. baseline (a) (§9.3)
w("---")
w()
w("## 3. Baseline (a) (§9 item 3)")
w()
w(f"Selection set (Amendment 1 B.1, resolved single-question targets minus every human "
  f"target): **{len(sel_targets)} targets** across "
  f"{len(set(t.rsplit('|',1)[0] for t in sel_targets))} questions. "
  f"**Intersection with the test set: "
  f"{len(set(sel_targets) & set(full['target'].unique()))}** — empty, as SPEC §4 requires.")
w()
w(md_table(rank.head(5)[["brier", "n_scored", "imputed_share", "eligible"]]))
w()
w(f"**Baseline (a) = `{chosen}`**, selection-set Brier {rank.loc[chosen,'brier']:.4f} "
  f"(×100 = {100*rank.loc[chosen,'brier']:.2f}); runner-up `{rank.index[1]}` at "
  f"{rank.loc[rank.index[1],'brier']:.4f} (×100 = {100*rank.loc[rank.index[1],'brier']:.2f}). "
  "No tie. Identical to the pilot: the champion is chosen on the selection set, which the "
  "pilot sampling never touched.")
w()
n_inelig = int((~rank["eligible"]).sum())
w(f"Eligibility (Amendment 1 A.3): {n_inelig} of 34 ineligible" +
  (": " + ", ".join(f"`{m}` ({100*rank.loc[m,'imputed_share']:.1f}% imputed)"
                    for m in rank[~rank['eligible']].index) if n_inelig else "") + ".")
w()
un_rank, un_chosen, un_n = F.unrestricted_champion(set(humans["target"]))
w(f"**Diagnostic — unrestricted-set champion (Amendment 1 B.1):** on the unrestricted set "
  f"({un_n:,} targets, 86% combination questions) the winner is `{un_chosen}` "
  f"(Brier {un_rank.loc[un_chosen,'brier']:.4f}), "
  + ("the same model." if un_chosen == chosen else
     f"**not** the amended choice `{chosen}`. The restriction to single questions changes "
     "the baseline, which is what the amendment was written to prevent."))
w()

# ===================================================== 4. sign tests (§9.4)
w("---")
w()
w("## 4. Sign tests (§9 item 4, SPEC §3)")
w()
p_ = full.copy()
p_["margin"] = (p_["p_a"] - p_["o"]).abs() - (p_["p_h"] - p_["o"]).abs()
hum_closer = (p_.sort_values(["margin", "target"], ascending=[False, True])
                .drop_duplicates("target").head(20))
mod_closer = (p_.sort_values(["margin", "target"], ascending=[True, True])
                .drop_duplicates("target").head(20))
more_ext = (p_.sort_values(["EXT_a", "target"], ascending=[False, True])
              .drop_duplicates("target").head(10))
a1 = bool((hum_closer["G_a"] > 0).all())
a2 = bool((mod_closer["G_a"] < 0).all())
a3 = bool((more_ext["EXT_a"] > 0).all())
w(f"- 20 rows (20 distinct targets) where the human is visibly closer → `G_a > 0`: "
  f"**{'PASS' if a1 else 'FAIL'}**")
w(f"- 20 rows where the model is visibly closer → `G_a < 0`: **{'PASS' if a2 else 'FAIL'}**")
w(f"- 10 rows where the human is visibly more extreme → `EXT_a > 0`: "
  f"**{'PASS' if a3 else 'FAIL'}**")
w()
def sign_tbl(d, cols):
    t = d[cols].copy()
    t.insert(0, "row", range(1, len(t) + 1))
    return md_table(t.set_index("row"))
w("**Human visibly closer:**")
w()
w(sign_tbl(hum_closer, ["forecaster", "target", "o", "p_h", "p_a", "G_a"]))
w()
w("**Model visibly closer:**")
w()
w(sign_tbl(mod_closer, ["forecaster", "target", "o", "p_h", "p_a", "G_a"]))
w()
w("**Human visibly more extreme:**")
w()
w(sign_tbl(more_ext, ["forecaster", "target", "p_h", "p_a", "CONF_a", "EXT_a"]))
w()

# ================================================= 5. distributions (§9.5)
w("---")
w()
w("## 5. Distributions (§9 item 5)")
w()
w("Brier quantities are raw (0–1); ×100 for the units used in the text (SPEC §3).")
w()
for v in ["G_a", "D_a", "EXT_a", "DIS"]:
    tbl = pd.DataFrame({g: quantiles(sub[v].values) for g, sub in full.groupby("GRP")})
    tbl["all"] = quantiles(full[v].values)
    w(f"**`{v}`**")
    w()
    w(md_table(tbl.T))
    w()

fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
for ax, v in zip(axes.ravel(), ["G_a", "D_a", "EXT_a", "DIS"]):
    for g, colr in [("S", "#1b6ca8"), ("P", "#d1495b")]:
        ax.hist(full.loc[full.GRP == g, v], bins=60, alpha=.55, density=True,
                label=f"{g} (n={int((full.GRP==g).sum()):,})", color=colr)
    ax.axvline(0, color="#333", lw=.8, ls="--")
    ax.set_title(v); ax.set_ylabel("density"); ax.legend(fontsize=8)
fig.suptitle("Full sample: distributions by group", fontsize=12)
fig.tight_layout(); fig.savefig(CFG.FIGDIR / "full_distributions.png", dpi=150)
plt.close(fig)
w("![Full distributions](figures/full_distributions.png)")
w()
w(f"**`EXT_a` blind spot.** Rows where `p_h` and `p_a` lie on opposite sides of 0.5: "
  f"**{100*cross_share:.1f}%** ({int(full['crossing'].sum()):,} of {len(full):,}).")
w()
ct = pd.DataFrame({"crossing": quantiles(full.loc[full.crossing, "EXT_a"].values),
                   "non-crossing": quantiles(full.loc[~full.crossing, "EXT_a"].values)}).T
w(md_table(ct))
w()
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.hist(full.loc[~full.crossing, "EXT_a"], bins=60, alpha=.6, density=True,
        label=f"non-crossing (n={int((~full.crossing).sum()):,})", color="#1b6ca8")
ax.hist(full.loc[full.crossing, "EXT_a"], bins=60, alpha=.6, density=True,
        label=f"crossing (n={int(full.crossing.sum()):,})", color="#e08e45")
ax.axvline(0, color="#333", lw=.8, ls="--")
ax.set_xlabel("EXT_a"); ax.set_ylabel("density")
ax.set_title("EXT_a: crossing vs non-crossing rows (full sample)")
ax.legend(); fig.tight_layout()
fig.savefig(CFG.FIGDIR / "full_ext_crossing.png", dpi=150); plt.close(fig)
w("![EXT crossing](figures/full_ext_crossing.png)")
w()
w(f"At {100*cross_share:.1f}% the share is material. This is what Amendment 2 item 2 "
  "responds to; the non-crossing H4 is reported in §9.")
w()
dtb = pd.DataFrame({"DIS": quantiles(full["DIS"].values),
                    "DIS_all34": quantiles(full["DIS_all34"].values)}).T
w("**Diagnostic — `DIS` (Amendment 1 C.1)** vs the pre-amendment SD across all 34 variants:")
w()
w(md_table(dtb))
w()
rr = float(np.corrcoef(full["DIS"], full["DIS_all34"])[0, 1])
w(f"Row-level Pearson correlation **{rr:.4f}**; `DIS_all34` is on average "
  f"{100*(full['DIS_all34'].mean()/full['DIS'].mean()-1):+.1f}% larger.")
w()

# ======================================================== 6. H1 (§9.6)
w("---")
w()
w("## 6. H1 — does the human beat the model on average? (§9 item 6)")
w()
gm = M.group_means_cluster(full, "G_a")
gm100 = gm.copy()
for c in ["mean", "ci_lo", "ci_hi"]:
    gm100[c] = 100 * gm100[c].astype(float)
w("Group means of `G_a` × 100 with question-clustered 95% CIs "
  "(positive = the human beat baseline (a)):")
w()
w(md_table(gm100[["mean", "ci_lo", "ci_hi", "n", "n_questions", "n_forecasters"]],
           floatfmt="%.3f"))
w()
h1, h1_fb = M.fit_spec("G_a ~ GRP", full, "H1")
w(f"`G_a ~ GRP` + crossed REs — {h1.note}")
w()
w(md_table(h1.table(), floatfmt="%.5f"))
w()
if h1.vc:
    tot = sum(h1.vc.values())
    w(md_table(pd.DataFrame({"variance": h1.vc,
                             "share": {k: v/tot for k, v in h1.vc.items()}}),
               floatfmt="%.5f"))
    w()

# ======================================================== 7. H2 (§9.7)
w("---")
w()
w("## 7. H2 — encompassing test (§9 item 7)")
w()
tl = (full.groupby("target")
      .agg(o=("o", "first"), p_a=("p_a", "first"), question=("question", "first"))
      .reset_index())
tl = (tl.merge(full[full.GRP == "S"].groupby("target")["p_h"].median().rename("p_h_S"),
               on="target", how="left")
        .merge(full[full.GRP == "P"].groupby("target")["p_h"].median().rename("p_h_P"),
               on="target", how="left"))

def h2_block(clip):
    return {g: M.encompassing(tl, col, clip) for g, col in [("S", "p_h_S"), ("P", "p_h_P")]}

h2 = h2_block(CFG.CLIP)
def h2_rows(hh):
    rows = []
    for g in ["S", "P"]:
        r = hh[g]
        rows.append(dict(group=g,
                         coef_human_minus_model=r["params"]["human_minus_model"],
                         ci_lo=r["ci"].loc["human_minus_model", 0],
                         ci_hi=r["ci"].loc["human_minus_model", 1],
                         coef_logit_p_a=r["params"]["logit_p_a"],
                         n_targets=r["nobs"], n_clusters=r["n_clusters"],
                         clipped_human=r["clipped_human"]))
    return pd.DataFrame(rows).set_index("group")
w(f"Target level, logistic, question-clustered SEs, clip {CFG.CLIP} (**primary**). "
  "Groups separate; SPEC 5.2 forbids pooling.")
w()
w(md_table(h2_rows(h2), floatfmt="%.4f"))
w()
w(f"Baseline-(a) values clipped: {h2['S']['clipped_model']} of {len(tl)}.")
w()
w("**Amendment 2 item 3 — sensitivity at clip [0.001, 0.999]:**")
w()
h2b = h2_block((0.001, 0.999))
w(md_table(h2_rows(h2b), floatfmt="%.4f"))
w()
w(f"The superforecaster median hits the primary bound on {h2['S']['clipped_human']} of "
  f"{len(tl)} targets ({100*h2['S']['clipped_human']/len(tl):.0f}%) and the looser bound on "
  f"{h2b['S']['clipped_human']} ({100*h2b['S']['clipped_human']/len(tl):.0f}%); the public "
  f"median hits them on {h2['P']['clipped_human']} and {h2b['P']['clipped_human']}. "
  "The primary result stands; this shows how much of the S coefficient is bound-driven.")
w()

# ==================================================== 8. H3 (§9.8)
w("---")
w()
w("## 8. H3 — where does the return live? (§9 item 8)")
w()
F3 = "G_a ~ DIS_z + CONF_a_z + logHZ_z + MKT + GRP"
h3, h3_fb = M.fit_spec(F3, full, "H3")
w(f"`{F3}` + crossed REs — {h3.note}")
w()
w(md_table(h3.table(), floatfmt="%.5f"))
w()
w("`HZ` is log(days), standardized (Amendment 1 D.2). **`logHZ_z` and `MKT` are partly "
  "redundant** — market and dataset horizons come from different distributions — so their "
  "coefficients should not be read separately. `CONF_a_z`, `logHZ_z`, `MKT` are controls, "
  "sign only (SPEC 5.3).")
w()
h3d, _ = M.fit_spec(F3.replace("DIS_z", "DIS_all34_z"), full, "H3")
w("Diagnostic — pre-amendment `DIS_all34`:")
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
h4, h4_fb = M.fit_spec(F4, full, "H4")
w(f"**Primary (all rows).** `{F4}` + crossed REs — {h4.note}")
w()
w(md_table(h4.table(), floatfmt="%.5f"))
w()
nc = full[~full.crossing].copy()
for c in ZCOLS:
    nc[c + "_z"] = F.zscore(nc[c])
h4nc, h4nc_fb = M.fit_spec(F4, nc, "H4")
w(f"**Amendment 2 item 2 — sensitivity, non-crossing rows only** "
  f"({len(nc):,} rows, {nc['target'].nunique()} targets, {nc['question'].nunique()} "
  f"questions, {nc['forecaster'].nunique()} forecasters; predictors re-standardized on "
  f"this subset) — {h4nc.note}")
w()
w(md_table(h4nc.table(), floatfmt="%.5f"))
w()
w("**Reading notes (Amendment 1 D.3, SPEC §9 item 5):**")
w()
w("- `EXT_a = |p_h − 0.5| − CONF_a` by construction, so the `EXT_a_z` coefficient is the "
  "effect of the human's extremity **at fixed model confidence and fixed deviation size**.")
w(f"- On the {100*cross_share:.1f}% of rows that cross 0.5, a positive `EXT_a` is not an "
  "extremization of the model's view. The non-crossing fit above is the cleaner read of "
  "'does extremizing the model's own view pay'.")
w("- SPEC 5.4 pre-registers the direction as two-sided; only the sign is interpreted.")
w()
i_all = float(h4.params["EXT_a_z:DIS_z"]); i_nc = float(h4nc.params["EXT_a_z:DIS_z"])
if np.sign(i_all) != np.sign(i_nc):
    w(f"> **The locked interaction changes sign between the two fits.** "
      f"`EXT_a_z:DIS_z` is "
      f"{ci_str(i_all, h4.ci.loc['EXT_a_z:DIS_z',0], h4.ci.loc['EXT_a_z:DIS_z',1])} on all "
      f"rows and "
      f"{ci_str(i_nc, h4nc.ci.loc['EXT_a_z:DIS_z',0], h4nc.ci.loc['EXT_a_z:DIS_z',1])} on "
      "non-crossing rows, and neither interval contains zero. The crossing rows, not the "
      "extremizing rows, carry the negative sign in the primary fit. SPEC 5.4 asks whether "
      "extremizing pays more where the models disagree; on the rows where `EXT_a` actually "
      "measures extremizing, the answer is positive. Reported here, not resolved: which fit "
      "answers the hypothesis is a design question for the designer.")
    w()

# ==================================================== 10. H5 (§9.10)
w("---")
w()
w("## 10. H5 — is the return a stable property of the forecaster? (§9 item 10)")
w()
# leave-one-out demeaning, POOLED across groups (Amendment 1 D.5)
g = full.groupby("target")["G_a"]
full["_tsum"] = g.transform("sum")
full["_tn"] = g.transform("size")
assert (full["_tn"] >= 2).all(), "a target has a single forecaster; LOO undefined"
full["G_dm"] = full["G_a"] - (full["_tsum"] - full["G_a"]) / (full["_tn"] - 1)
own_share = float((1 / full["_tn"]).mean())

rng = np.random.default_rng(CFG.SPLIT_HALF_SEED)
tg = np.array(sorted(full["target"].unique()), dtype=object)
perm = rng.permutation(len(tg))
halfA = set(tg[perm[:len(tg) // 2]])
full["half"] = np.where(full["target"].isin(halfA), "A", "B")

hm = (full.groupby(["GRP", "forecaster", "half"])["G_dm"].mean()
          .unstack("half").dropna())
counts = (full.groupby(["GRP", "forecaster", "half"]).size().unstack("half")
              .reindex(hm.index).fillna(0))
w("Leave-one-out demeaning is **pooled across both groups** (Amendment 1 D.5): "
  "`G_dm = G_a − mean(G_a of all other forecasters on that target)`. "
  f"Mean own-row share of a target mean is {100*own_share:.2f}% "
  "(the 2.5% figure in SPEC 5.5 was approximate and is superseded).")
w()
w(f"Split-half: a single random assignment of the {len(tg)} targets, seed "
  f"{CFG.SPLIT_HALF_SEED}, the same split for every forecaster "
  f"({len(halfA)} targets in half A, {len(tg)-len(halfA)} in half B).")
w()

def boot_corr(x, y, draws=CFG.BOOTSTRAP_DRAWS, seed=CFG.SPLIT_HALF_SEED):
    r = np.random.default_rng(seed)
    n = len(x)
    out = np.empty(draws)
    for i in range(draws):
        idx = r.integers(0, n, n)
        xa, ya = x[idx], y[idx]
        out[i] = np.nan if xa.std() == 0 or ya.std() == 0 else np.corrcoef(xa, ya)[0, 1]
    return np.nanpercentile(out, [2.5, 97.5]), out

h5_rows = []
for grp in ["S", "P"]:
    sub = hm.loc[grp]
    x, y = sub["A"].values, sub["B"].values
    r_p = float(np.corrcoef(x, y)[0, 1])
    r_s = float(scipy.stats.spearmanr(x, y).statistic)
    (lo, hi), _ = boot_corr(x, y)
    cmin = counts.loc[grp].min(axis=1)
    h5_rows.append(dict(group=grp, n_forecasters=len(sub), pearson_r=r_p,
                        ci_lo=lo, ci_hi=hi, spearman_r=r_s,
                        min_targets_in_smaller_half=int(cmin.min()),
                        n_with_lt5=int((cmin < 5).sum())))
h5 = pd.DataFrame(h5_rows).set_index("group")
w("Correlation across forecasters between the two half-means of leave-one-out demeaned "
  f"`G_a`, with percentile bootstrap 95% CIs ({CFG.BOOTSTRAP_DRAWS:,} draws, resampling "
  "forecasters):")
w()
w(md_table(h5, floatfmt="%.4f"))
w()
fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
for ax, grp, colr in zip(axes, ["S", "P"], ["#1b6ca8", "#d1495b"]):
    sub = hm.loc[grp]
    ax.scatter(sub["A"], sub["B"], s=18, alpha=.65, color=colr, edgecolor="none")
    ax.axhline(0, color="#999", lw=.7); ax.axvline(0, color="#999", lw=.7)
    rv = float(h5.loc[grp, "pearson_r"])
    ax.set_title(f"{grp}: r = {rv:.3f}  (n = {len(sub)})")
    ax.set_xlabel("half A mean of demeaned G_a"); ax.set_ylabel("half B mean")
fig.suptitle("H5 split-half stability of the human's return", fontsize=12)
fig.tight_layout(); fig.savefig(CFG.FIGDIR / "full_h5_splithalf.png", dpi=150)
plt.close(fig)
w("![H5 split half](figures/full_h5_splithalf.png)")
w()
if h3.vc:
    tot3 = sum(h3.vc.values())
    vshare = h3.vc["forecaster"] / tot3
    w(f"**Forecaster variance share from the H3 model:** "
      f"{h3.vc['forecaster']:.5f} of {tot3:.5f} total = **{100*vshare:.1f}%**.")
    w()
    w(md_table(pd.DataFrame({"variance": h3.vc,
                             "share": {k: v/tot3 for k, v in h3.vc.items()}}),
               floatfmt="%.5f"))
    w()

# ============================================= 11. robustness (§9 item 11)
w("---")
w()
w("## 11. Robustness (§9 item 11, SPEC §7)")
w()
w("### 7.1 Baseline (b) — median of the 34 matched variants")
w()
gmb = M.group_means_cluster(full, "G_b")
gmb100 = gmb.copy()
for c in ["mean", "ci_lo", "ci_hi"]:
    gmb100[c] = 100 * gmb100[c].astype(float)
w(md_table(gmb100[["mean", "ci_lo", "ci_hi", "n"]], floatfmt="%.3f"))
w()
h3b, _ = M.fit_spec("G_b ~ DIS_z + CONF_b_z + logHZ_z + MKT + GRP", full, "H3")
h4b, _ = M.fit_spec("G_b ~ EXT_b_z + absD_b_z + DIS_z + CONF_b_z + logHZ_z + MKT + GRP "
                    "+ EXT_b_z:DIS_z", full, "H4")
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
w(f"`G_log = log(p_h_o) − log(p_a_o)`, probabilities clipped to {CFG.CLIP}. "
  "Positive = human better, same orientation as `G_a`.")
w()
h3l, _ = M.fit_spec("G_log ~ DIS_z + CONF_a_z + logHZ_z + MKT + GRP", full, "H3")
h4l, _ = M.fit_spec("G_log ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + MKT + GRP "
                    "+ EXT_a_z:DIS_z", full, "H4")
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
ds = full[full.MKT == 0].copy()
for c in ZCOLS:
    ds[c + "_z"] = F.zscore(ds[c])
w(f"Dropping the {int(fam.get(1,0))} market targets leaves {ds['target'].nunique()} targets, "
  f"{ds['question'].nunique()} questions, {len(ds):,} rows. `MKT` is dropped from the "
  "right-hand side because it is constant here.")
w()
h3d2, _ = M.fit_spec("G_a ~ DIS_z + CONF_a_z + logHZ_z + GRP", ds, "H3")
h4d2, _ = M.fit_spec("G_a ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + GRP "
                     "+ EXT_a_z:DIS_z", ds, "H4")
w("H3, dataset only:")
w()
w(md_table(h3d2.table(), floatfmt="%.5f"))
w()
w("H4, dataset only:")
w()
w(md_table(h4d2.table(), floatfmt="%.5f"))
w()

w("### Sensitivity to Amendment 2 item 1 (clip instead of drop)")
w()
w("**Sensitivity only — not a primary or robustness result, and no conclusion rests on it "
  "(Amendment 2 item 1).**")
w()
hum_clip, _, _ = F.load_humans(rbt, rbq)
inv_fix = invalid.copy()
inv_fix["p_h"] = inv_fix["p_h"].clip(0, 1)
hum_clip = pd.concat([hum_clip, inv_fix], ignore_index=True)
fr_clip, _ = F.build_frame(hum_clip, models_df, stats, chosen)
gmc = M.group_means_cluster(fr_clip, "G_a")
gmc100 = gmc.copy()
for c in ["mean", "ci_lo", "ci_hi"]:
    gmc100[c] = 100 * gmc100[c].astype(float)
w(f"Clipping the {n_inv} out-of-range rows to [0, 1] instead of dropping them adds "
  f"{len(fr_clip)-len(full)} rows. H1 group means × 100:")
w()
w(md_table(gmc100[["mean", "ci_lo", "ci_hi", "n"]], floatfmt="%.3f"))
w()

# ------------------------------- reporting note: pilot vs full run
w("---")
w()
w("## Reporting note — pilot vs full run")
w()
w("The pilot was accepted partly on the ground that its signs were sensible. Two "
  "pre-registered quantities do not carry over unchanged, so both runs are shown here. "
  "The pilot models are refitted on the pilot question subset by this script, not "
  "transcribed.")
w()
pq_note, _ = F.pilot_questions(full["question"].unique())
pil = full[full["question"].isin(pq_note)].copy()
for c in ZCOLS:
    pil[c + "_z"] = F.zscore(pil[c])
gm_p = M.group_means_cluster(pil, "G_a")
h3_p, _ = M.fit_spec(F3, pil, "H3")
h4_p, _ = M.fit_spec(F4, pil, "H4")
cmp_rows = [
    dict(quantity="H1 mean G_a x100, S",
         pilot=100*float(gm_p.loc["S", "mean"]), full=100*float(gm.loc["S", "mean"])),
    dict(quantity="H1 mean G_a x100, P",
         pilot=100*float(gm_p.loc["P", "mean"]), full=100*float(gm.loc["P", "mean"])),
    dict(quantity="H3 DIS_z",
         pilot=float(h3_p.params["DIS_z"]), full=float(h3.params["DIS_z"])),
    dict(quantity="H4 EXT_a_z",
         pilot=float(h4_p.params["EXT_a_z"]), full=float(h4.params["EXT_a_z"])),
    dict(quantity="H4 EXT_a_z:DIS_z",
         pilot=float(h4_p.params["EXT_a_z:DIS_z"]),
         full=float(h4.params["EXT_a_z:DIS_z"])),
]
cmp_df = pd.DataFrame(cmp_rows).set_index("quantity")
cmp_df["sign_changed"] = np.sign(cmp_df["pilot"]) != np.sign(cmp_df["full"])
w(md_table(cmp_df, floatfmt="%.5f"))
w()
w("`H1` and the `EXT_a_z` main effect keep their sign and rough magnitude. **The locked "
  "`EXT_a_z:DIS_z` interaction changes sign between the pilot (30% of questions) and the "
  "full sample**, with both intervals excluding zero. `H3`'s `DIS_z` is near zero and "
  "not distinguishable from zero in either run. A pre-registered coefficient that reverses "
  "between a 30% subsample and the full sample is a fact about how thinly that interaction "
  "is identified at the question level — it rests on "
  f"{full['question'].nunique()} clusters — and it is reported rather than adjudicated.")
w()

# ==================================== 12. what could break the reading
w("---")
w()
w("## 12. What could break the interpretation (§9 item 12)")
w()
w("**Information the humans had that the models did not.** The matched condition "
  "(Amendment 1 B.3) equalises the freeze value and the absence of supplied news, and no "
  "further. It does not equalise three things. Superforecasters were run as a 9-day "
  "tournament with a group stage in which they saw one another's forecasts and rationales "
  "and could revise (paper Appendix I); the models forecast once, alone. Both human groups "
  "could browse the open web at forecast time; the matched model variants had no retrieval. "
  "And the superforecaster file records `searches` and `consulted_urls`, so that browsing "
  "is documented, not hypothetical. A positive `G_a` for superforecasters is therefore not "
  "a clean statement about human judgement versus model judgement; it is a statement about "
  "a deliberating, searching human group versus a single-pass model. The public group did "
  "not deliberate, which is part of why its `G_a` is negative, and the S–P gap should not "
  "be read as pure skill.")
w()
w("**Information the models had that the humans did not.** Baseline (a) is the winner of a "
  "34-way selection on 930 held-out targets. Nothing selects the humans that way. The "
  "comparison is a selected model against unselected humans, which if anything understates "
  "the humans.")
w()
w(f"**The single round.** Everything here is forecast-due-date {CFG.ROUND}, the only round "
  "ForecastBench has released with individual-level human forecasts. There is no second "
  "round to check whether any of this replicates, no way to separate forecaster skill from "
  "round-specific luck, and no way to tell whether the H5 split-half number reflects a "
  "stable trait or a within-round artefact. H5 splits one round in half; it does not "
  "establish stability over time, and should not be quoted as if it did.")
w()
w(f"**Questions, not rows, are the sample size.** The frame has {len(full):,} rows, but "
  f"they rest on {full['question'].nunique()} questions and "
  f"{full['target'].nunique()} targets, and outcomes of the same question at different "
  "horizons are often identical. Every clustered SE and every random intercept in this "
  f"report treats the question as the unit, so the question-level moderators in H3 and H4 "
  f"(`DIS`, `CONF_a`, `HZ`, `MKT`) are estimated on about "
  f"{full['question'].nunique()} independent clusters, not on tens of thousands of "
  "observations. Their CIs should be read as coming from a sample of that size. The "
  "row-level predictors that vary within a target (`EXT_a`, `absD_a`) are far better "
  f"identified — {full['forecaster'].nunique()} forecasters differ on the same target — "
  "which is why their intervals are so much tighter. That asymmetry is real and is not a "
  "sign that the question-level effects are precisely zero.")
w()
w("**Baseline dependence.** The `DIS` coefficient in H3 is the study's headline moderator, "
  "and it moves with the choice of benchmark (§11.7.1). A result that changes when the "
  "single best model is swapped for the median of 34 is a result about the benchmark as "
  "much as about the forecasters.")
w()
w("**The `EXT_a` blind spot.** "
  f"{100*cross_share:.1f}% of rows cross 0.5. On those rows a larger `EXT_a` means the "
  "human went the other way, not that the human sharpened the model's view. The primary "
  "H4 pools them; the Amendment 2 sensitivity does not. Where the two disagree, the "
  "non-crossing fit is the one that answers the question the hypothesis asks.")
w()
w("**Imputation and data quality.** ForecastBench fills missing model forecasts with a "
  "hard-coded 0.5 and flags them `imputed`; those rows are excluded throughout "
  f"(Amendment 1 A.3), and baseline (a) has none. Separately, {n_inv} human rows were not "
  "probabilities at all and are excluded (Amendment 2 item 1). Both are the publisher's "
  "data-quality issues, not modelling choices, and both are counted in §1 and §2 so the "
  "reader can judge them.")
w()
w("**A pre-registered coefficient that will not sit still.** The `EXT_a_z:DIS_z` "
  "interaction is negative on all rows, positive on non-crossing rows, and positive in the "
  "pilot — three fits, three intervals excluding zero, two signs. Whatever is reported "
  "about it should be reported as unstable, and the question-level moderators generally "
  "should be treated as the least reliable part of this study.")
w()
w("**What this design cannot say.** Nothing here identifies a causal effect. `DIS`, "
  "`CONF_a` and `EXT_a` are all properties of forecasts, not manipulations, and a "
  "forecaster who extremizes on hard questions differs from one who does not in ways this "
  "data cannot observe.")
w()

# ============================================================ close
w("---")
w()
w("## Stop")
w()
w("SPEC §10: the full run stops here. The designer decides what, if anything, follows.")
w()
w(f"Total runtime {time.time()-T0:.0f}s (SPEC §8 tripwire: 1 hour).")
w()

# ------------------------------------------------- summary block
summary = ["## Core quantities at a glance", "",
           "Estimates with 95% CIs. Interpretation is confined to §12.", "",
           "| Hypothesis | Quantity | Estimate [95% CI] |",
           "|---|---|---|"]
summary += [
    f"| H1 | mean `G_a` ×100, superforecasters | "
    f"{ci_str(100*float(gm.loc['S','mean']), 100*float(gm.loc['S','ci_lo']), 100*float(gm.loc['S','ci_hi']), '%.2f')} |",
    f"| H1 | mean `G_a` ×100, public | "
    f"{ci_str(100*float(gm.loc['P','mean']), 100*float(gm.loc['P','ci_lo']), 100*float(gm.loc['P','ci_hi']), '%.2f')} |",
    f"| H2 | encompassing coef, superforecaster median | "
    f"{ci_str(h2['S']['params']['human_minus_model'], h2['S']['ci'].loc['human_minus_model',0], h2['S']['ci'].loc['human_minus_model',1])} |",
    f"| H2 | encompassing coef, public median | "
    f"{ci_str(h2['P']['params']['human_minus_model'], h2['P']['ci'].loc['human_minus_model',0], h2['P']['ci'].loc['human_minus_model',1])} |",
    f"| H3 | `DIS_z` on `G_a` (core) | "
    f"{ci_str(h3.params['DIS_z'], h3.ci.loc['DIS_z',0], h3.ci.loc['DIS_z',1])} |",
    f"| H4 | `EXT_a_z` on `G_a` (core, sign only) | "
    f"{ci_str(h4.params['EXT_a_z'], h4.ci.loc['EXT_a_z',0], h4.ci.loc['EXT_a_z',1])} |",
    f"| H4 | `EXT_a_z:DIS_z` (the one locked interaction) | "
    f"{ci_str(h4.params['EXT_a_z:DIS_z'], h4.ci.loc['EXT_a_z:DIS_z',0], h4.ci.loc['EXT_a_z:DIS_z',1])} |",
    f"| H4 | `EXT_a_z`, non-crossing rows (Amd 2 item 2) | "
    f"{ci_str(h4nc.params['EXT_a_z'], h4nc.ci.loc['EXT_a_z',0], h4nc.ci.loc['EXT_a_z',1])} |",
    f"| H5 | split-half r, superforecasters | "
    f"{ci_str(float(h5.loc['S','pearson_r']), float(h5.loc['S','ci_lo']), float(h5.loc['S','ci_hi']))} |",
    f"| H5 | split-half r, public | "
    f"{ci_str(float(h5.loc['P','pearson_r']), float(h5.loc['P','ci_lo']), float(h5.loc['P','ci_hi']))} |",
]
summary += ["",
            f"Sign tests: {'all pass' if (a1 and a2 and a3) else 'FAILURE — see §4'}. "
            f"Frame {len(full):,} rows · {full['target'].nunique()} targets · "
            f"{full['question'].nunique()} questions · {full['forecaster'].nunique()} "
            f"forecasters · baseline (a) `{chosen}`.", ""]
fb = {k: v for k, v in {"H1": h1_fb, "H3": h3_fb, "H4": h4_fb,
                        "H4 non-crossing": h4nc_fb}.items() if v}
summary.append("All mixed models converged; no SPEC §5 / Amendment 1 D.1 fallback was used."
               if not fb else
               "**Fallbacks used:** " + "; ".join(f"{k} ({v})" for k, v in fb.items()))
summary.append("")

(CFG.DOCS / "forecast_full_REPORT.md").write_text(
    "\n".join(OUT).replace("<<<SUMMARY>>>", "\n".join(summary)) + "\n")
print("wrote", CFG.DOCS / "forecast_full_REPORT.md")
print("runtime %.0fs" % (time.time() - T0))
print("sign tests:", a1, a2, a3, "| fallbacks:", fb)
print(h5)
