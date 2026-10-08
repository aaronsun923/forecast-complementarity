"""SPEC v3 Amendment 7: per-variant per-forecaster gain, with intervals.

Locked in specs/forecast_spec_v3.md at f4044ee (amendment) and 1db593d (clarification), before
this file was written or run. Note 2 (820e868, after results, descriptive) adds the reference's
substitution log gain. Nothing here changes a v1, v2 or P5 number.

Reads the existing derived frame (data/derived/full_frame.pkl, the v1 H1 frame) and the 34
matched-variant forecasts through the v1/v2 loaders. No new download.

Usage:  python3 code/amendment7.py
Writes: docs/amendment7_REPORT.md, docs/amendment7_pervariant.csv, docs/figures/amd7_gain_curve.png
"""
import subprocess
import sys
import time
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as CFG
import fbdata as F
import models as M
import v2common as V
import v2full as W
from report import md_table

T0 = time.time()
warnings.filterwarnings("ignore")
SPEC_COMMITS = {"amendment": "f4044ee4cf418bfd0d9cc2eabe2c2f1955c33a1a",
                "clarification": "1db593d6209cd688e0cfc352f74821f6d6636093",
                "note2": "820e868aa60df58fe95c6ad86bc0be9167f94e91"}
M1 = "Claude-3-5-Sonnet-20240620 (zero shot with freeze values)"
LOCKED_H1 = {"S": (3.38, 1.36, 5.41), "P": (-7.81, -9.69, -5.92)}     # v1 H1, spec text
SEED = 20260906               # Amendment 7: bootstrap seed
FOLD_SEED = 20260908          # v2 cross-fit folds (v2full.crossfit_gain), as in v2 Amendment 2
DRAWS = 2000
MIN_REF = 10                  # v2 Amendment 2
A2_REF_GAIN_SLOPE = (1.2076, 0.8766, 1.5386)    # docs/forecast_v2_full_REPORT.md, Amendment 2
LO, HI = CFG.CLIP

OUT = []
def w(s=""):
    OUT.append(s)


def stop(msg):
    print("STOP:", msg, flush=True)
    sys.exit(msg)


# ==================================================================== load
full = pd.read_pickle(CFG.DERIVED / "full_frame.pkl")
if len(full) != 33334 or full["target"].nunique() != 578 or full["question"].nunique() != 162:
    stop(f"derived frame is not the v1 H1 frame: {len(full)} rows, {full['target'].nunique()} targets")
mods, meta = F.load_matched_models()
hum_targets = set(full["target"])
rank, chosen, _ = F.select_baseline_a(mods, hum_targets)
assert chosen == M1
tab = V.build_variant_table(full, mods, meta, rank, hum_targets)       # Q_m, base, scaffold
variants = list(tab.index)
assert len(variants) == 34
test = mods[mods["target"].isin(hum_targets)]
questions = sorted(full["question"].unique())
qmap = {q: i for i, q in enumerate(questions)}
n_q = len(questions)
rng = np.random.default_rng(SEED)
PICKS = rng.integers(0, n_q, (DRAWS, n_q))       # one set of question draws for every quantity


def boot_mean(values, qcodes):
    """Mean over rows and its question-cluster bootstrap percentile interval (shared PICKS)."""
    s = np.bincount(qcodes, weights=values, minlength=n_q)
    n = np.bincount(qcodes, minlength=n_q)
    b = s[PICKS].sum(1) / n[PICKS].sum(1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    return float(s.sum() / n.sum()), float(lo), float(hi)


def variant_rows(m):
    """The v1 H1 frame with variant m in place of baseline (a): G_B and G_L as fbdata.build_frame
    defines G_a and G_log. Rows where m's forecast is imputed or missing are dropped."""
    fm = test[test["model"] == m].set_index("target")
    p = full["target"].map(fm["p"])
    imp = full["target"].map(fm["imputed"]).fillna(True).astype(bool)
    keep = p.notna() & ~imp
    d = full.loc[keep, ["GRP", "question", "target", "forecaster", "p_h", "o", "BS_h", "p_h_o"]].copy()
    pm = p[keep].to_numpy(float)
    d["G_B"] = 100 * ((pm - d["o"].to_numpy()) ** 2 - d["BS_h"].to_numpy())
    pmc = np.clip(pm, LO, HI)
    d["G_L"] = np.log(d["p_h_o"].to_numpy()) - np.log(np.where(d["o"] == 1, pmc, 1 - pmc))
    return d, int((~keep).sum())


# ============================================ reproduction check (clarified)
d1, drop1 = variant_rows(M1)
assert drop1 == 0
same_B = np.array_equal(d1["G_B"].to_numpy(), 100 * full["G_a"].to_numpy())
same_L = np.array_equal(d1["G_L"].to_numpy(), full["G_log"].to_numpy())
v1_ref = M.group_means_cluster(full.assign(G100=100 * full["G_a"]), "G100")   # v1 H1 itself
an = M.group_means_cluster(d1.rename(columns={"G_B": "G100"}), "G100")       # same method, A7 rows
REPRO = {}
for g in ("S", "P"):
    a7 = (float(an.loc[g, "mean"]), float(an.loc[g, "ci_lo"]), float(an.loc[g, "ci_hi"]))
    v1 = (float(v1_ref.loc[g, "mean"]), float(v1_ref.loc[g, "ci_lo"]), float(v1_ref.loc[g, "ci_hi"]))
    ok = (f"{a7[0]:.4f}" == f"{v1[0]:.4f}"
          and all(f"{x:.2f}" == f"{y:.2f}" for x, y in zip(a7, LOCKED_H1[g]))
          and all(f"{x:.4f}" == f"{y:.4f}" for x, y in zip(a7, v1)))
    REPRO[g] = (a7, v1, ok)
print("reproduction check:", {g: (f"{r[0][0]:.4f} [{r[0][1]:.2f}, {r[0][2]:.2f}]", r[2])
                              for g, r in REPRO.items()}, "rows bit-identical:", same_B, same_L, flush=True)
if not (same_B and same_L and all(r[2] for r in REPRO.values())):
    stop(f"Amendment 7 reproduction check failed: {REPRO}, rows identical G_B {same_B} G_L {same_L}")


# ============================================ item 1: per-variant per-forecaster gain
rows = []
for m in variants:
    d, dropped = variant_rows(m)
    qc = d["question"].map(qmap).to_numpy()
    r = dict(variant=m, base=tab.loc[m, "base"], scaffold=tab.loc[m, "scaffold"], Q=float(tab.loc[m, "Q_m"]),
             rows_dropped_imputed=dropped)
    for g in ("S", "P"):
        k = (d["GRP"] == g).to_numpy()
        r[f"n_rows_{g}"] = int(k.sum())
        for rule in ("G_B", "G_L"):
            est, lo, hi = boot_mean(d[rule].to_numpy()[k], qc[k])
            r[f"{rule}_{g}"], r[f"{rule}_{g}_lo"], r[f"{rule}_{g}_hi"] = est, lo, hi
    rows.append(r)
PV = pd.DataFrame(rows).sort_values("Q").reset_index(drop=True)
print(f"item 1 done {time.time() - T0:.0f}s", flush=True)


# ============================================ item 2: reference curve's own gain over m
tl = V.target_level(full)
P = np.column_stack([tl["target"].map(test[(test["model"] == m) & ~test["imputed"]].set_index("target")["p"])
                     .to_numpy(float) for m in variants])
OKv = np.isfinite(P)
REF = np.full_like(P, np.nan)
for j in range(P.shape[1]):
    others = np.delete(P, j, axis=1)
    med = np.nanmedian(others, axis=1)
    med[np.isfinite(others).sum(axis=1) < MIN_REF] = np.nan
    REF[:, j] = med
y_all = tl["o"].to_numpy(float)
qc_tl = tl["question"].map(qmap).to_numpy(np.int32)
LM, LR = V.logit_clip(P), V.logit_clip(REF)
KEEP = OKv & np.isfinite(REF)

gain_ref, gain_ref_se = np.full(34, np.nan), np.full(34, np.nan)
for j in range(34):
    k = KEEP[:, j]
    gg, ss = W.crossfit_gain(y_all[k], LM[k, j], LR[k, j], qc_tl[k], seed=FOLD_SEED)
    if gg is None:
        stop(f"reference cross-fitted gain not computable for {variants[j]}")
    gain_ref[j], gain_ref_se[j] = gg, ss
fit_ref = W.stage2(tab["Q_m"].to_numpy(float), gain_ref, gain_ref_se, tab["base"].to_numpy())
a2_check = tuple(round(fit_ref[k], 4) for k in ("slope", "slope_lo", "slope_hi"))
print("A2 reference gain slope:", a2_check, "vs report", A2_REF_GAIN_SLOPE, flush=True)
if a2_check != A2_REF_GAIN_SLOPE:
    stop(f"the v2 Amendment 2 reference object does not reproduce: slope {a2_check} vs {A2_REF_GAIN_SLOPE}")

def logscore(p, yy):
    q = np.clip(p, LO, HI)
    return np.log(np.where(yy == 1, q, 1 - q))


BS_m = (P - y_all[:, None]) ** 2
BS_r = (REF - y_all[:, None]) ** 2
idx_q = [np.flatnonzero(qc_tl == q) for q in range(n_q)]
BL = np.full((DRAWS, 34), np.nan)
for t in range(DRAWS):
    pick = PICKS[t]
    rws = np.concatenate([idx_q[q] for q in pick])
    clus = np.concatenate([np.full(len(idx_q[q]), i) for i, q in enumerate(pick)])
    for j in range(34):
        k = KEEP[rws, j]
        gg, _ = W.crossfit_gain(y_all[rws][k], LM[rws, j][k], LR[rws, j][k], clus[k], seed=FOLD_SEED)
        if gg is not None:
            BL[t, j] = gg
    if (t + 1) % 500 == 0:
        print(f"  reference bootstrap {t + 1}/{DRAWS} {time.time() - T0:.0f}s", flush=True)
n_fail = int(np.isnan(BL).sum())
refrows = []
for j, m in enumerate(variants):
    k = KEEP[:, j]
    bri = boot_mean(100 * (BS_m[k, j] - BS_r[k, j]), qc_tl[k])
    # Note 2: substitution gain, log score(reference) - log score(m), per target, same clip
    sub = boot_mean(logscore(REF[k, j], y_all[k]) - logscore(P[k, j], y_all[k]), qc_tl[k])
    llo, lhi = V.pct_ci(BL[:, j])
    refrows.append(dict(variant=m, Q=float(tab.loc[m, "Q_m"]), n_targets=int(k.sum()),
                        ref_G_B=bri[0], ref_G_B_lo=bri[1], ref_G_B_hi=bri[2],
                        ref_gain_log=float(gain_ref[j]), ref_gain_log_lo=llo, ref_gain_log_hi=lhi,
                        ref_sub_log=sub[0], ref_sub_log_lo=sub[1], ref_sub_log_hi=sub[2]))
RF = pd.DataFrame(refrows).sort_values("Q").reset_index(drop=True)
print(f"item 2 done {time.time() - T0:.0f}s (failed draws {n_fail})", flush=True)


# ============================================ item 3: counts; rule-disagreement check
def side(lo, hi):
    return "above zero" if lo > 0 else ("below zero" if hi < 0 else "includes zero")


crow = []
for g in ("S", "P"):
    for rule in ("G_B", "G_L"):
        s = [side(r[f"{rule}_{g}_lo"], r[f"{rule}_{g}_hi"]) for _, r in PV.iterrows()]
        crow.append(dict(group=g, rule=rule, **{k: s.count(k) for k in ("above zero", "below zero", "includes zero")}))
CNT = pd.DataFrame(crow)
dis = []
for _, r in PV.iterrows():
    for g in ("S", "P"):
        sb, sl = np.sign(r[f"G_B_{g}"]), np.sign(r[f"G_L_{g}"])
        xb = side(r[f"G_B_{g}_lo"], r[f"G_B_{g}_hi"]) != "includes zero"
        xl = side(r[f"G_L_{g}_lo"], r[f"G_L_{g}_hi"]) != "includes zero"
        if sb != sl or xb != xl:
            dis.append(dict(variant=r["variant"], group=g, Q=r["Q"],
                            G_B=f"{r[f'G_B_{g}']:+.2f} [{r[f'G_B_{g}_lo']:+.2f}, {r[f'G_B_{g}_hi']:+.2f}]",
                            G_L=f"{r[f'G_L_{g}']:+.3f} [{r[f'G_L_{g}_lo']:+.3f}, {r[f'G_L_{g}_hi']:+.3f}]",
                            sign_differs=bool(sb != sl), exclusion_differs=bool(xb != xl)))
DIS = pd.DataFrame(dis)


# ==================================================================== outputs
csv = PV.merge(RF.drop(columns="Q"), on="variant").sort_values("Q")
csv.to_csv(CFG.DOCS / "amendment7_pervariant.csv", index=False, float_format="%.6f")

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for ax, rule, rcol, ylab in ((axes[0], "G_B", "ref_G_B", "Brier gain ×100 (positive favours the human)"),
                             (axes[1], "G_L", "ref_sub_log", "log-score gain (positive favours the human)")):
    for g, col in (("S", "#1b6ca8"), ("P", "#d1495b")):
        ax.errorbar(PV["Q"], PV[f"{rule}_{g}"], yerr=[PV[f"{rule}_{g}"] - PV[f"{rule}_{g}_lo"],
                                                     PV[f"{rule}_{g}_hi"] - PV[f"{rule}_{g}"]],
                    fmt="o", ms=4, color=col, ecolor=col, elinewidth=.8, capsize=0,
                    label={"S": "superforecasters", "P": "public"}[g])
    ax.errorbar(RF["Q"], RF[rcol], yerr=[RF[rcol] - RF[f"{rcol}_lo"], RF[f"{rcol}_hi"] - RF[rcol]],
                fmt="^", ms=4, color="#5b5b5b", ecolor="#999", elinewidth=.8, capsize=0,
                label="reference (median of the other 33) in place of m, per target")
    ax.axhline(0, color="#999", lw=.8, ls="--")
    ax.set_xlabel("$Q_m$ (selection-set Brier; lower = better)")
    ax.set_ylabel(ylab)
    ax.legend(fontsize=8)
axes[0].set_title("Brier")
axes[1].set_title("log score")
fig.suptitle("Amendment 7: gain over each of the 34 matched variants, 95% question-cluster bootstrap intervals",
             fontsize=11)
fig.tight_layout()
fig.savefig(CFG.FIGDIR / "amd7_gain_curve.png", dpi=150)
plt.close(fig)

head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=CFG.REPO_ROOT).stdout.strip()


def ci(e, lo, hi, f):
    return f"{e:+{f}} [{lo:+{f}}, {hi:+{f}}]"


w("# SPEC v3 Amendment 7: per-variant per-forecaster gain")
w()
w(f"Spec: amendment `{SPEC_COMMITS['amendment']}`, clarification `{SPEC_COMMITS['clarification']}` "
  "(specs/forecast_spec_v3.md, both committed before this code was written or run); Note 2 "
  f"`{SPEC_COMMITS['note2']}` (after results, descriptive addition). "
  f"Repo HEAD at run: `{head}`. No v1, v2 or P5 number changes.")
w()
w("## Reproduction check (first)")
w()
w("As clarified: G_B against M1 reproduces v1 H1 in the point estimate (to four decimals) and in v1 H1's own "
  "analytic question-clustered interval (`models.group_means_cluster`) recomputed on the Amendment 7 rows. "
  f"The Amendment 7 per-row G_B and G_L for M1 are also bit-identical to the frame's `G_a` ×100 and `G_log`: "
  f"{'yes' if same_B and same_L else 'NO'}.")
w()
w("| group | Amendment 7, analytic | v1 H1 (locked) | match |")
w("|---|---|---|---|")
for g, (a7, v1, ok) in REPRO.items():
    w(f"| {g} | {a7[0]:+.4f} [{a7[1]:.2f}, {a7[2]:.2f}] | {v1[0]:+.4f} [{v1[1]:.2f}, {v1[2]:.2f}] | "
      f"{'yes' if ok else 'NO'} |")
w()
w("Reference object check: the v2 Amendment 2 reference cross-fitted log-score gain, rebuilt here, gives the "
  f"stage-2 slope {a2_check[0]:.4f} [{a2_check[1]:.4f}, {a2_check[2]:.4f}], equal to the Amendment 2 report.")
w()
w("## Setup")
w()
w(f"- Frame: `data/derived/full_frame.pkl`, the v1 H1 frame ({len(full):,} forecaster-target rows, "
  f"{full['target'].nunique()} targets, {n_q} questions; v1 Amendment 2 row exclusions applied). "
  "For each variant m the frame is reused with m's forecast in place of baseline (a); rows where m's forecast is "
  "imputed or missing are dropped for that variant only.")
w(f"- G_B(m) = Brier(m) − Brier(human) per row, ×100. G_L(m) = log score(human) − log score(m) per row, "
  f"probabilities clipped to [{LO}, {HI}]. Both exactly as `fbdata.build_frame` defines G_a and G_log.")
w(f"- Intervals: question-level cluster bootstrap, {DRAWS} draws, seed {SEED}, percentile 95%. One set of "
  "question draws serves every variant, group and quantity, items 1 and 2 alike.")
w(f"- Reference (item 2): leave-one-out median of the other 33 variants on each target (v2 Amendment 2; at least "
  f"{MIN_REF} contributing variants), on targets where m has a non-imputed forecast. Log score: the cross-fitted "
  f"out-of-sample gain from adding the reference to a logistic recalibration of m (`v2full.crossfit_gain`, 5 folds "
  f"by question, fold seed {FOLD_SEED}); within each bootstrap draw the folds are reassigned on the draw's "
  f"clusters, as in Amendment 2. Brier: mean over targets of Brier(m) − Brier(reference), ×100, no fitting "
  f"(the spec does not name a cross-fitted Brier; this reading is chosen here and flagged). Failed draws: {n_fail}.")
w(f"- Note 2 (`{SPEC_COMMITS['note2']}`, after results, descriptive, no estimate changes): the cross-fitted "
  "log-score gain above is a combination gain (reference added to m), while G_L is a substitution gain (human in "
  "place of m). The reference's substitution gain, log score(reference) − log score(m) per target under the same "
  "clip, is added as the last column of the item 2 table with the same bootstrap, and is what the log panel of the "
  "figure plots beside the human G_L. The Brier panel already compares substitution with substitution.")
w("- Variants are ordered by selection-set Q (v1 §4 Brier on the 930-target selection set).")
w()
w("## Locked reading (restated)")
w()
w("- 34 variants are not 34 independent tests. The paper reports the curve and the counts, with the variants "
  "ordered by selection-set Q. No per-variant p-values enter the paper.")
w("- Recorded expectation from the v2 point estimates: superforecasters positive against all 34 under Brier; "
  "public positive against about 6 and negative against about 28. The counts below show whether the sign flip "
  "for the public group survives the intervals; the paper reports them whatever they are.")
w("- Scoring-rule check for Section 5: if no variant moves between rules, Section 5 gets one sentence; if any "
  "does, the variant is named.")
w()
w("## Counts (item 3): variants of 34 by where the 95% interval lies")
w()
w(md_table(CNT, index=False))
w()
w("## Scoring-rule check")
w()
if DIS.empty:
    w("No variant moves: for every variant and group the sign of the point estimate is the same under G_B and G_L, "
      "and the interval excludes zero under both rules or under neither.")
else:
    w(f"{len(DIS)} variant-group pairs move between rules (sign of the point estimate differs, or the interval "
      "excludes zero under one rule and not the other):")
    w()
    w(md_table(DIS, index=False, floatfmt="%.4f"))
for g, name in (("S", "Superforecasters"), ("P", "Public")):
    w()
    w(f"## {name}: gain over each variant (item 1)")
    w()
    w("| variant | scaffold | Q | n rows | G_B ×100 [95% CI] | G_L [95% CI] |")
    w("|---|---|---|---|---|---|")
    for _, r in PV.iterrows():
        mark = " ¹" if r["variant"] == M1 else ""
        w(f"| {r['base']}{mark} | {r['scaffold']} | {r['Q']:.4f} | {r[f'n_rows_{g}']:,} | "
          f"{ci(r[f'G_B_{g}'], r[f'G_B_{g}_lo'], r[f'G_B_{g}_hi'], '.2f')} | "
          f"{ci(r[f'G_L_{g}'], r[f'G_L_{g}_lo'], r[f'G_L_{g}_hi'], '.3f')} |")
    a7 = REPRO[g][0]
    w()
    w(f"¹ M1 (benchmark (a)). Analytic question-clustered interval (v1 H1 method) for G_B: "
      f"{a7[0]:+.2f} [{a7[1]:+.2f}, {a7[2]:+.2f}]; the bootstrap interval is in the table.")
w()
w("## Reference curve's own gain over each variant (item 2)")
w()
w("Reference minus m: positive means the median of the other 33 variants beats m.")
w()
w("| variant | scaffold | Q | n targets | Brier gain ×100 [95% CI] | cross-fitted log-score gain [95% CI] | "
  "substitution log-score gain [95% CI] (Note 2) |")
w("|---|---|---|---|---|---|---|")
for _, r in RF.iterrows():
    w(f"| {tab.loc[r['variant'], 'base']} | {tab.loc[r['variant'], 'scaffold']} | {r['Q']:.4f} | {r['n_targets']} | "
      f"{ci(r['ref_G_B'], r['ref_G_B_lo'], r['ref_G_B_hi'], '.2f')} | "
      f"{ci(r['ref_gain_log'], r['ref_gain_log_lo'], r['ref_gain_log_hi'], '.4f')} | "
      f"{ci(r['ref_sub_log'], r['ref_sub_log_lo'], r['ref_sub_log_hi'], '.3f')} |")
w()
w("![Amendment 7 gain curve](figures/amd7_gain_curve.png)")
w()
w("All numbers: `docs/amendment7_pervariant.csv`. Rows dropped for imputed forecasts, per variant: "
  + ", ".join(f"{r['base']} ({r['scaffold']}) {r['rows_dropped_imputed']}" for _, r in PV.iterrows()
              if r["rows_dropped_imputed"]) + ("" if PV["rows_dropped_imputed"].any() else "none") + ".")
w()
w(f"Runtime {time.time() - T0:.0f}s.")
(CFG.DOCS / "amendment7_REPORT.md").write_text("\n".join(OUT) + "\n")
print("wrote docs/amendment7_REPORT.md", flush=True)
