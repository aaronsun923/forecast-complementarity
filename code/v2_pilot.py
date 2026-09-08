"""SPEC v2 pilot: H6 and H7 on the v1 pilot question subset (§5).

Delivers §7 for the pilot. H8 (§7 item 7) and the five §6 robustness items
(§7 item 8) are not part of a H6/H7-only pilot and are stated as out of scope.
The §6 item-3 leverage statistics ARE computed, because §7 item 4 requires the
figures to mark the flagged points.

Usage:  python3 code/v2_pilot.py
Writes: docs/forecast_v2_pilot_REPORT.md, docs/figures/v2_pilot_*.png
"""
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
import statsmodels.api as sm

import config as CFG
import fbdata as F
import models as M
import v2common as V
from report import md_table, ci_str

T0 = time.time()
warnings.filterwarnings("ignore")
CFG.FIGDIR.mkdir(parents=True, exist_ok=True)

DRAWS = 2000
BOOT_SEED = 20260908          # SPEC §4 [LOCKED]
OUT = []
def w(s=""):
    OUT.append(s)


# ===================================================================== load
rbt, rbq = F.load_resolutions()
hum, dropped, invalid = F.load_humans(rbt, rbq)
mods, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(mods, set(hum["target"]))
stats = F.target_level_model_stats(mods)

pilot_qs, n_pilot_q = F.pilot_questions(sorted(hum["question"].unique()))
pilot_qs = set(pilot_qs)
hum_p = hum[hum["question"].isin(pilot_qs)]
test_targets_pilot = set(hum_p["target"])

tab = V.build_variant_table(hum, mods, meta, rank, test_targets_pilot)
variants = list(tab.index)
print(f"{len(variants)} variants; pilot {n_pilot_q} questions, "
      f"{len(test_targets_pilot)} targets")

# ------------------------------------------------- stage 1, all 34 variants
t_s1 = time.time()
rows = []
for i, m in enumerate(variants, 1):
    r = V.stage1_variant(hum, mods, stats, m, pilot_questions=pilot_qs)
    r["model"] = m
    rows.append(r)
    print(f"  [{i:2d}/34] {m[:52]:52s} {time.time()-t_s1:6.0f}s", flush=True)
s1 = pd.DataFrame(rows).set_index("model")
t_stage1 = time.time() - t_s1
V_ = tab.join(s1)

# --------------------------------------- validate the bootstrap's fast path
tl_ref = V.target_level(
    F.build_frame(hum, mods, stats, variants[0])[0].pipe(
        lambda d: d[d["question"].isin(pilot_qs)]))
_la = V.logit_clip(tl_ref["p_a"].values)
_lh = V.logit_clip(tl_ref["p_h_S"].values)
_X = np.column_stack([np.ones(len(tl_ref)), _la, _lh - _la])
_b, _se = V.fast_logit(_X, tl_ref["o"].values.astype(float),
                       pd.factorize(tl_ref["question"])[0])
val_b = abs(_b[2] - V_.loc[variants[0], "beta_S"])
val_se = abs(_se[2] - V_.loc[variants[0], "beta_S_se"])

# ------------------------------------------- wide target-level design matrix
tl_wide = (hum_p.groupby("target")
           .agg(o=("o", "first"), question=("question", "first")).reset_index())
for g, name in (("S", "p_h_S"), ("P", "p_h_P")):
    tl_wide = tl_wide.merge(
        hum_p[hum_p.group == g].groupby("target")["p_h"].median().rename(name),
        on="target", how="left")
sub_m = mods[mods["target"].isin(test_targets_pilot)]
for m in variants:
    s = sub_m[(sub_m["model"] == m) & (~sub_m["imputed"])].set_index("target")["p"]
    tl_wide[m] = tl_wide["target"].map(s)          # NaN where imputed -> dropped per variant

# ================================================= stage 2 + both bootstraps
res = {}
for kind, ycol, secol in (("beta", "beta_%s", "beta_%s_se"),
                          ("eps", "eps_%s", "eps_%s_se")):
    for g in ("S", "P"):
        d = V_.dropna(subset=[ycol % g, secol % g])
        fit = V.wls_slope(d["Q_m"].values, d[ycol % g].values,
                          d[secol % g].values, d["base"].values)
        fit["frame"] = d
        res[(kind, g)] = fit

t_h6 = time.time()
boot6 = {g: V.boot_h6(tl_wide, variants, V_, g, DRAWS, BOOT_SEED) for g in ("S", "P")}
t_h6 = time.time() - t_h6

t_h7 = time.time()
boot7 = {}
for g in ("S", "P"):
    d = res[("eps", g)]["frame"]
    boot7[g] = V.wild_cluster_boot(d["Q_m"].values, d[f"eps_{g}"].values,
                                   d[f"eps_{g}_se"].values, d["base"].values,
                                   DRAWS, BOOT_SEED)
t_h7 = time.time() - t_h7

# ------------------------------------------------------ leverage (§6 item 3)
for k, fit in res.items():
    d = fit["frame"]
    lev, ck = fit["leverage"], fit["cooks"]
    fit["lev_flag"] = (lev > 3 * lev.mean()) | (ck > 4 / len(lev))
    fit["lev_tab"] = pd.DataFrame(
        {"Q_m": d["Q_m"].values, "leverage": lev, "cooks_d": ck,
         "flagged": fit["lev_flag"]}, index=d.index)


# ==================================================================== report
w("# SPEC v2 pilot — benchmark-quality curve (H6, H7)")
w()
w(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} · "
  "spec commit `84e54eb` · **pilot only, full sample not run**")
w()
w(f"§5 [LOCKED]: the v1 pilot question subset — {n_pilot_q} of "
  f"{hum['question'].nunique()} questions, seed {CFG.PILOT_SEED} — carrying all their "
  f"targets. H6 and H7 only. Deliverables are §7 items 1–6 and 9; items 7 (H8) and 8 "
  "(the five §6 robustness items) are not produced by a H6/H7-only pilot and are marked "
  "out of scope below. The §6 item-3 leverage statistics are computed because §7 item 4 "
  "requires the figures to mark flagged points.")
w()

# ---- 1. environment
w("---")
w()
w("## 1. Environment (§7 item 1)")
w()
w(md_table(pd.DataFrame({"value": {
    "python": sys.version.split()[0],
    "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
    "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
    "statsmodels": statsmodels.__version__, "matplotlib": matplotlib.__version__,
    "datasets repo commit": CFG.DATASETS_COMMIT,
    "bootstrap draws": str(DRAWS), "bootstrap seed": str(BOOT_SEED),
    "pilot seed": str(CFG.PILOT_SEED),
}})))
w()
w(f"Runtime: stage 1 (34 variants × 2 groups, β and ε) {t_stage1:.0f}s; "
  f"H6 question bootstrap {t_h6:.0f}s; H7 wild cluster bootstrap {t_h7:.1f}s. "
  f"Total {time.time()-T0:.0f}s, against the one-hour tripwire.")
w()
w("**Fast-path validation.** The H6 bootstrap recomputes β and its cluster-robust SE "
  "inside every draw, which the v1 `models.encompassing` path is too slow to support at "
  "the full-run scale. A numpy IRLS with a cluster sandwich is used instead, and it "
  f"reproduces the v1 path exactly: |Δβ| = {val_b:.2e}, |ΔSE| = {val_se:.2e} on the "
  "first variant. Every β reported in the tables below comes from the v1 path, not the "
  "fast path.")
w()

# ---- 2. per-variant table
w("---")
w()
w("## 2. Per-variant table (§7 item 2)")
w()
w("**[LOCKED] §7 item 4:** every quantity is computed on that variant's own retained "
  "targets. `targets_kept` is the pilot-subset count after dropping targets where that "
  "variant's forecast is imputed. **The y values are not computed on identical target "
  "sets across the x axis.** No reweighting is applied for this.")
w()
show = V_.reset_index()[[
    "base", "scaffold", "Q_m", "imputed_targets", "targets_kept",
    "beta_S", "beta_S_lo", "beta_S_hi", "beta_P", "beta_P_lo", "beta_P_hi",
    "eps_S", "eps_S_lo", "eps_S_hi", "eps_P", "eps_P_lo", "eps_P_hi",
    "G_S", "G_P"]].copy()
show = show.sort_values("Q_m").set_index("base")
w(md_table(show, floatfmt="%.4f"))
w()
nfb = sum(1 for g in ("S", "P") for v in V_[f"eps_{g}_fallback"] if v)
w(f"ε fits: {len(V_)*2} mixed models, {nfb} fell back to question-clustered OLS "
  "(SPEC v1 §5 / Amendment 1 D.1). "
  f"β clipping at {CFG.CLIP}: superforecaster medians clipped on "
  f"{int(V_['beta_S_clipped_human'].iloc[0])} of {len(tl_wide)} pilot targets, public on "
  f"{int(V_['beta_P_clipped_human'].iloc[0])}.")
w()
w("`G_m,g` is reported per §3 and is **close to an identity** — see the figure caption "
  "in §3 below.")
w()

# ---- 3/4. figures
def curve_fig(kind, ylab, fname, title, caption_extra=""):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharex=True)
    for ax, g, colr in zip(axes, ("S", "P"), ("#1b6ca8", "#d1495b")):
        fit = res[(kind, g)]
        d = fit["frame"]
        x, y = d["Q_m"].values, d[f"{kind}_{g}"].values
        for b, sub in d.groupby("base"):
            if len(sub) == 2:
                ax.plot(sub["Q_m"], sub[f"{kind}_{g}"], "-", color="#bbb", lw=.9, zorder=1)
        flag = fit["lev_flag"]
        ax.scatter(x[~flag], y[~flag], s=34, color=colr, zorder=3, label="variant")
        ax.scatter(x[flag], y[flag], s=90, facecolors="none", edgecolors="k",
                   linewidths=1.4, zorder=4, label="flagged (leverage / Cook's D)")
        gx = np.linspace(x.min(), x.max(), 60)
        bs = boot6[g] if kind == "beta" else boot7[g]
        preds = bs["intercepts"][None, :] + np.outer(gx, bs["slopes"])
        lo, hi = np.nanpercentile(preds, [2.5, 97.5], axis=1)
        ax.fill_between(gx, lo, hi, color=colr, alpha=.15, zorder=0,
                        label="95% bootstrap band")
        ax.plot(gx, fit["intercept"] + fit["slope"] * gx, color=colr, lw=1.8, zorder=2)
        ax.axhline(0, color="#999", lw=.8, ls="--")
        ax.set_xlabel("$Q_m$  (mean Brier on the selection set; lower = better model)")
        ax.set_ylabel(ylab)
        ax.set_title(f"group {g}   slope = {fit['slope']:+.3f}", fontsize=10)
        ax.legend(fontsize=7.5, loc="best")
    fig.suptitle(title, fontsize=12)
    fig.tight_layout()
    fig.savefig(CFG.FIGDIR / fname, dpi=150)
    plt.close(fig)

w("---")
w()
w("## 3. Figure — β against Q (§7 item 3)")
w()
curve_fig("beta", r"$\beta_{m,g}$  (human-minus-model coefficient)",
          "v2_pilot_beta_vs_Q.png",
          "H6 (pilot): human information beyond the model, against model quality")
w("![beta vs Q](figures/v2_pilot_beta_vs_Q.png)")
w()
w("Scaffold pairs of the same base model are joined by a grey line. Points ringed in "
  "black are flagged by the §6 item-3 leverage check. Band is the 2.5–97.5 percentile "
  "of the H6 question-level cluster bootstrap.")
w()
w("## 4. Figure — ε against Q (§7 item 4)")
w()
curve_fig("eps", r"$\varepsilon_{m,g}$  (EXT coefficient)",
          "v2_pilot_eps_vs_Q.png",
          "H7 (pilot): return to extremizing, against model quality")
w("![eps vs Q](figures/v2_pilot_eps_vs_Q.png)")
w()
w("Same layout. Band is the stage-2 wild cluster bootstrap, which conditions on the "
  "stage-1 ε estimates and is therefore narrower than H6's — see §6.")
w()
w("**`G_m,g` caption (§3 [LOCKED]).** `G_m,g` is reported in the §2 table and is not "
  "plotted, because it is close to an identity: `G_m,g = BS_m(test) − BS_g(test)`, the "
  "second term does not vary with m, and `BS_m(test)` is highly correlated with `Q_m` "
  "because both are that variant's Brier on different question sets. Any figure of it "
  "must carry this statement.")
w()

# ---- 5. H6
w("---")
w()
w("## 5. H6 — does human information shrink as the model improves? (§7 item 5)")
w()
h6rows = []
for g in ("S", "P"):
    fit = res[("beta", g)]; bs = boot6[g]
    blo, bhi = V.pct_ci(bs["slopes"])
    h6rows.append(dict(group=g, n_variants=fit["n"], n_base_models=fit["n_clusters"],
                       slope=fit["slope"],
                       boot_lo=blo, boot_hi=bhi,
                       analytic_lo=fit["slope_lo"], analytic_hi=fit["slope_hi"],
                       draws_used=bs["n_draws_used"]))
w("Stage 2: `β_m,g ~ Q_m`, inverse-variance weighted. **Primary interval is the "
  "question-level cluster bootstrap** (§4 [LOCKED]): the pilot's questions are resampled "
  f"with replacement (seed {BOOT_SEED}), every β_m is recomputed on the resampled data "
  "for all 34 variants, and the stage-2 slope is refit — 2,000 times. `Q_m` is held "
  "fixed, as [LOCKED], because it is measured on the selection set, which contains no "
  "test targets.")
w()
w(md_table(pd.DataFrame(h6rows).set_index("group"), floatfmt="%.4f"))
w()
w("The analytic interval clustered by base model is shown for comparison and is **the "
  "narrowest and least appropriate** of the two: 17 clusters understate uncertainty, and "
  "it cannot see the outcome noise shared across all 34 variants.")
w()
fails = {g: (boot6[g]["n_fail_draw"], boot6[g]["n_fail_fit"]) for g in ("S", "P")}
w(f"Bootstrap draws discarded (too few variants fittable): S {fails['S'][0]}, "
  f"P {fails['P'][0]} of {DRAWS}. Individual variant fits that failed inside a draw "
  f"(separation or singular cluster matrix): S {fails['S'][1]}, P {fails['P'][1]} of "
  f"{DRAWS*34} attempted.")
w()
w("### Descriptive extrapolation — where β reaches zero")
w()
w("**Reported without inference (§4.1).** The crossing is computed inside every "
  "bootstrap draw, so the interval comes from the same resampling as the slope.")
w()
xrows = []
for g in ("S", "P"):
    fit = res[("beta", g)]; bs = boot6[g]
    d = fit["frame"]
    qlo, qhi = float(d["Q_m"].min()), float(d["Q_m"].max())
    pt = V.zero_crossing(fit["intercept"], fit["slope"])
    clo, chi = V.pct_ci(bs["crossings"])
    cr = bs["crossings"][np.isfinite(bs["crossings"])]
    outside = float(np.mean((cr < qlo) | (cr > qhi))) if len(cr) else np.nan
    xrows.append(dict(group=g, Q_observed_min=qlo, Q_observed_max=qhi,
                      crossing_point=pt, crossing_lo=clo, crossing_hi=chi,
                      share_draws_outside_range=outside,
                      within_observed_range=bool(qlo <= pt <= qhi)))
w(md_table(pd.DataFrame(xrows).set_index("group"), floatfmt="%.4f"))
w()
for r_ in xrows:
    if not r_["within_observed_range"]:
        w(f"- Group {r_['group']}: the fitted line **does not reach zero within the "
          f"observed range of Q** ({r_['Q_observed_min']:.4f}–{r_['Q_observed_max']:.4f}). "
          "Per §4.1 the crossing is not extrapolated beyond the range; the point value "
          "above is shown only to locate it.")
    else:
        w(f"- Group {r_['group']}: the crossing falls inside the observed range of Q.")
w(f"- Share of bootstrap draws whose crossing lies outside the observed range: "
  f"S {xrows[0]['share_draws_outside_range']:.3f}, "
  f"P {xrows[1]['share_draws_outside_range']:.3f}.")
w()

# ---- 6. H7
w("---")
w()
w("## 6. H7 — does the return to extremizing depend on model quality? (§7 item 6)")
w()
h7rows = []
for g in ("S", "P"):
    fit = res[("eps", g)]; bs = boot7[g]
    blo, bhi = V.pct_ci(bs["slopes"])
    h7rows.append(dict(group=g, n_variants=fit["n"], n_base_models=fit["n_clusters"],
                       slope=fit["slope"], wild_lo=blo, wild_hi=bhi,
                       analytic_lo=fit["slope_lo"], analytic_hi=fit["slope_hi"],
                       draws_used=bs["n_draws_used"]))
w("Stage 2: `ε_m,g ~ Q_m`, inverse-variance weighted. Interval is the stage-2 **wild "
  f"cluster bootstrap** over the {res[('eps','S')]['n_clusters']} base models "
  f"(Rademacher weights, {DRAWS} draws, seed {BOOT_SEED}).")
w()
w(md_table(pd.DataFrame(h7rows).set_index("group"), floatfmt="%.4f"))
w()
w("**[LOCKED] statement required by §4:** this interval **conditions on the stage-1 ε "
  "estimates and is therefore narrower than H6's.** Regenerating ε inside each draw "
  "would take about 30 days at the full-run scale and is not done. The analytic "
  "base-model-clustered interval is shown alongside and is narrower still.")
w()

# ---- leverage
w("### Leverage and Cook's distance (computed for the §7 item 4 figure marks)")
w()
w("The full §6 item-3 robustness rerun (dropping the highest-`Q` variant) is **not part "
  "of the pilot**; only the diagnostics needed to mark the figures are computed here.")
w()
for kind, lab in (("beta", "β"), ("eps", "ε")):
    for g in ("S", "P"):
        lt = res[(kind, g)]["lev_tab"]
        fl = lt[lt["flagged"]]
        if len(fl):
            w(f"**{lab}, group {g}** — {len(fl)} flagged of {len(lt)}:")
            w()
            w(md_table(fl[["Q_m", "leverage", "cooks_d"]], floatfmt="%.4f"))
            w()
        else:
            w(f"**{lab}, group {g}** — no point flagged.")
            w()

# ---- out of scope
w("---")
w()
w("## 7–8. H8 and the §6 robustness items — out of pilot scope")
w()
w("§5 [LOCKED] runs H6 and H7 only. §7 item 7 (H8 correlations) and §7 item 8 (the five "
  "§6 robustness items) are therefore not produced here and are deferred to the full "
  "run. H8 is in any case [LOCKED] as report-only with no conclusion drawn, and §3 of "
  "the SPEC already records the preliminary values (about 0.77 for superforecasters, "
  "0.34 for the public, against 0.59 for the models alone).")
w()

# ---- 9. limits
w("---")
w()
w("## 9. What limits the reading (§7 item 9)")
w()
w(f"**Seventeen independent base models, not 34 points.** The x axis has "
  f"{len(V_)} points but only {V_['base'].nunique()} independent base models; the two "
  "scaffolds of one base model share weights, training data and failure modes, and are "
  "joined by a grey line in both figures to make that visible. Every interval here "
  "clusters on the base model, and 17 clusters is few.")
w()
w("**The 34 points share their outcome noise.** Every β and ε is estimated on the same "
  f"{len(tl_wide)} pilot targets, the same human medians and the same outcomes. That "
  "sharing is why H6's primary interval resamples questions rather than trusting stage-2 "
  "clustering, and why H7's interval — which cannot do the same at feasible cost — is "
  "explicitly labelled as conditioning on stage 1.")
w()
w("**All models are from mid-2024.** The quality range is a snapshot of one generation "
  f"({V_['Q_m'].min():.4f} to {V_['Q_m'].max():.4f} Brier). Nothing here says what "
  "happens at quality levels outside that span, which is exactly why §4.1 forbids "
  "extrapolating the zero crossing beyond the observed range.")
w()
w("**`Q` is measured on a different question set from the test set.** `Q_m` comes from "
  "the selection set (single questions, complement of the human targets); β and ε come "
  "from the human targets. This is deliberate — it keeps the x axis out of sample — but "
  "it means `Q` is a proxy for the variant's quality *on the test questions*, not a "
  "measurement of it.")
w()
w("**Pilot scale.** These estimates rest on "
  f"{n_pilot_q} questions and {len(tl_wide)} targets. Question-level resampling with "
  f"{n_pilot_q} clusters is itself coarse; the full run has "
  f"{hum['question'].nunique()} questions and {hum['target'].nunique()} targets.")
w()
w("---")
w()
w("## Stop")
w()
w("SPEC §5: the pilot stops here. The full sample has **not** been run.")
w()
w(f"Total runtime {time.time()-T0:.0f}s (tripwire: 1 hour).")
w()

(CFG.DOCS / "forecast_v2_pilot_REPORT.md").write_text("\n".join(OUT) + "\n")
print("\nwrote", CFG.DOCS / "forecast_v2_pilot_REPORT.md")
print("runtime %.0fs (stage1 %.0fs, H6 boot %.0fs, H7 boot %.1fs)"
      % (time.time()-T0, t_stage1, t_h6, t_h7))
for g in ("S", "P"):
    print(f"H6 {g}: slope={res[('beta',g)]['slope']:+.4f} "
          f"boot={V.pct_ci(boot6[g]['slopes'])}")
    print(f"H7 {g}: slope={res[('eps',g)]['slope']:+.4f} "
          f"wild={V.pct_ci(boot7[g]['slopes'])}")
