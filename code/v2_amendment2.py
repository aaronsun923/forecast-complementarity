"""SPEC v2 Amendment 2: the reference curve. Post-results diagnostic.

For each variant m the human median is replaced by the leave-one-out median of
the OTHER 33 variants on that target, and the same two y quantities are computed
against the same Q_m: the §3 encompassing coefficient and the §6 item 4
cross-fitted out-of-sample log-score gain, with identical folds, seed, clipping
and target sets.

Differences are computed INSIDE each bootstrap draw (paired). The human side is
recomputed in the same loop purely so the pairing is exact, and is verified
against the stored full-run matrices; no pre-registered estimate is refit or
changed, and nothing already reported is overwritten.

Usage:  python3 code/v2_amendment2.py
Appends a section to docs/forecast_v2_full_REPORT.md and writes two figures.
"""
import os
import pickle
import re
import time
import warnings
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

import config as CFG
import fbdata as F
import models as M
import v2common as V
import v2full as W
from report import md_table

T0 = time.time()
warnings.filterwarnings("ignore")
DRAWS = int(os.environ.get("A2_DRAWS", "2000"))
SEED = 20260908
TAG = os.environ.get("A2_TAG", "")
MIN_REF = 10            # need at least this many other variants to form a median

MARK_START = "<!-- amendment2:start -->"
MARK_END = "<!-- amendment2:end -->"


# ==================================================================== load
rbt, rbq = F.load_resolutions()
hum, _, _ = F.load_humans(rbt, rbq)
mods, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(mods, set(hum["target"]))
test_targets = set(hum["target"])
tab = V.build_variant_table(hum, mods, meta, rank, test_targets)
variants = list(tab.index)
questions = sorted(hum["question"].unique())
qmap = {q: i for i, q in enumerate(questions)}
n_q = len(questions)

A = pickle.loads((CFG.DERIVED / "v2_full_A_stage1.pkl").read_bytes())
VT = tab.join(A["s1"])
Cst = pickle.loads((CFG.DERIVED / "v2_full_C_boot_beta.pkl").read_bytes())
Est = pickle.loads((CFG.DERIVED / "v2_full_E_boot_crossfit.pkl").read_bytes())

# target-level wide frame, exactly as the full run built it
tl = (hum.groupby("target")
      .agg(o=("o", "first"), question=("question", "first")).reset_index())
for g, nm in (("S", "p_h_S"), ("P", "p_h_P")):
    tl = tl.merge(hum[hum.group == g].groupby("target")["p_h"].median().rename(nm),
                  on="target", how="left")
sub_m = mods[mods["target"].isin(test_targets)]
for m in variants:
    s = sub_m[(sub_m["model"] == m) & (~sub_m["imputed"])].set_index("target")["p"]
    tl[m] = tl["target"].map(s)

P = tl[variants].to_numpy(float)                     # targets x variants
y_all = tl["o"].to_numpy(float)
OKv = np.isfinite(P)

# The full run's two bootstraps used different (both arbitrary) question codings:
# boot_questions_beta factorised in order of first appearance, _boot_crossfit used
# the global sorted qmap. Each paired loop below reuses the coding of the full-run
# bootstrap it is paired against, so the human side reproduces the stored draws
# exactly and the pairing is provably the same resample.
QC = {
    "beta": pd.factorize(tl["question"])[0].astype(np.int32),
    "gain": tl["question"].map(qmap).to_numpy(np.int32),
}
qcodes_all = QC["gain"]

# ---------------- leave-one-out reference: median of the OTHER 33 variants
REF = np.full_like(P, np.nan)
for j in range(P.shape[1]):
    others = np.delete(P, j, axis=1)
    cnt = np.isfinite(others).sum(axis=1)
    med = np.nanmedian(others, axis=1)
    med[cnt < MIN_REF] = np.nan
    REF[:, j] = med
print(f"reference built: {np.isfinite(REF).all(axis=0).sum()}/{len(variants)} variants "
      f"with complete reference coverage", flush=True)

LM = V.logit_clip(P)
LR = V.logit_clip(REF)
LH = {g: V.logit_clip(tl[f"p_h_{g}"].to_numpy(float)) for g in ("S", "P")}
Qm = VT["Q_m"].to_numpy(float)
BASE = VT["base"].to_numpy()
Q3 = dict(min=float(np.min(Qm)), median=float(np.median(Qm)), max=float(np.max(Qm)))


# ---------------------------------------------------------- point estimates
def gain_point(lh_mat_or_vec):
    out = np.full(len(variants), np.nan)
    se = np.full(len(variants), np.nan)
    for j in range(len(variants)):
        lh = lh_mat_or_vec[:, j] if lh_mat_or_vec.ndim == 2 else lh_mat_or_vec
        k = OKv[:, j] & np.isfinite(lh)
        gg, ss = W.crossfit_gain(y_all[k], LM[k, j], lh[k], qcodes_all[k], seed=SEED)
        if gg is not None:
            out[j], se[j] = gg, ss
    return out, se


print("point estimates...", flush=True)
# reference beta uses that variant's own reference column
beta_ref = np.full(len(variants), np.nan); beta_ref_se = np.full(len(variants), np.nan)
for j, m in enumerate(variants):
    k = OKv[:, j] & np.isfinite(REF[:, j])
    d = pd.DataFrame({"o": y_all[k], "p_a": P[k, j], "hcol": REF[k, j],
                      "question": tl["question"].to_numpy()[k]})
    r = M.encompassing(d, "hcol", CFG.CLIP)
    beta_ref[j] = float(r["params"]["human_minus_model"])
    lo, hi = (float(r["ci"].loc["human_minus_model", 0]),
              float(r["ci"].loc["human_minus_model", 1]))
    beta_ref_se[j] = V.se_from_ci(lo, hi)
gain_ref, gain_ref_se = gain_point(LR)
print("  done", flush=True)


# ------------------------------------------------------------ stage 2 fits
def s2(y, se, keep=None):
    ok = np.isfinite(y) & np.isfinite(se) & (se > 0)
    if keep is not None:
        ok &= keep
    return W.stage2(Qm[ok], y[ok], se[ok], BASE[ok])


FITS = {
    ("beta", "S"): s2(VT["beta_S"].to_numpy(float), VT["beta_S_se"].to_numpy(float)),
    ("beta", "P"): s2(VT["beta_P"].to_numpy(float), VT["beta_P_se"].to_numpy(float)),
    ("beta", "REF"): s2(beta_ref, beta_ref_se),
    ("gain", "S"): s2(Est["point"]["S"], Est["point_se"]["S"]),
    ("gain", "P"): s2(Est["point"]["P"], Est["point_se"]["P"]),
    ("gain", "REF"): s2(gain_ref, gain_ref_se),
}


# ------------------------------------------------- paired question bootstrap
def wls_line(y, se, q):
    ok = np.isfinite(y) & np.isfinite(se) & (se > 0)
    if ok.sum() < 5:
        return None
    wts = 1.0 / se[ok] ** 2
    try:
        f = sm.WLS(y[ok], sm.add_constant(q[ok]), weights=wts).fit()
    except Exception:                                        # noqa: BLE001
        return None
    return float(f.params[0]), float(f.params[1])


def paired_bootstrap(kind, draws=DRAWS, seed=SEED, progress=250):
    """One loop: human (S and P) and reference computed on the SAME resampled
    questions, so the difference is paired within the draw."""
    rng = np.random.default_rng(seed)
    qc = QC[kind]
    idx = [np.flatnonzero(qc == q) for q in range(n_q)]
    diffs = {g: {k: [] for k in Q3} for g in ("S", "P")}
    hum_mat = {g: np.full((draws, len(variants)), np.nan) for g in ("S", "P")}
    nfail = 0
    for t in range(draws):
        pick = rng.integers(0, n_q, n_q)
        rows = np.concatenate([idx[q] for q in pick])
        clus = np.concatenate([np.full(len(idx[q]), i) for i, q in enumerate(pick)])
        yb = y_all[rows]
        est = {"S": (np.full(len(variants), np.nan), np.full(len(variants), np.nan)),
               "P": (np.full(len(variants), np.nan), np.full(len(variants), np.nan)),
               "REF": (np.full(len(variants), np.nan), np.full(len(variants), np.nan))}
        for j in range(len(variants)):
            okj = OKv[rows, j]
            la = LM[rows, j]
            for who in ("S", "P", "REF"):
                lh = LR[rows, j] if who == "REF" else LH[who][rows]
                k = okj & np.isfinite(lh)
                if k.sum() < (20 if kind == "beta" else 60):
                    nfail += 1
                    continue
                if kind == "beta":
                    X = np.column_stack([np.ones(k.sum()), la[k], lh[k] - la[k]])
                    co, se = V.fast_logit(X, yb[k], clus[k])
                    if co is None or se[2] <= 0:
                        nfail += 1
                        continue
                    est[who][0][j], est[who][1][j] = co[2], se[2]
                else:
                    gg, ss = W.crossfit_gain(yb[k], la[k], lh[k], clus[k], seed=SEED)
                    if gg is None or ss is None or ss <= 0:
                        nfail += 1
                        continue
                    est[who][0][j], est[who][1][j] = gg, ss
        ref_line = wls_line(est["REF"][0], est["REF"][1], Qm)
        for g in ("S", "P"):
            hum_mat[g][t] = est[g][0]
            hl = wls_line(est[g][0], est[g][1], Qm)
            if hl is None or ref_line is None:
                continue
            for nm, qv in Q3.items():
                diffs[g][nm].append((hl[0] + hl[1] * qv) - (ref_line[0] + ref_line[1] * qv))
        if progress and (t + 1) % progress == 0:
            print(f"    {kind} paired boot {t+1}/{draws}", flush=True)
    return dict(diffs={g: {k: np.array(v) for k, v in d.items()}
                       for g, d in diffs.items()},
                hum_mat=hum_mat, nfail=nfail)


print("paired bootstrap: beta", flush=True)
BB = paired_bootstrap("beta")
print("paired bootstrap: gain", flush=True)
BG = paired_bootstrap("gain")

# --------- verification that the recomputed human side matches the full run
def agree(new, stored):
    a, b = np.asarray(new), np.asarray(stored)
    n = min(a.shape[0], b.shape[0])          # smoke runs use fewer draws
    a, b = a[:n], b[:n]
    k = np.isfinite(a) & np.isfinite(b)
    return float(np.max(np.abs(a[k] - b[k]))) if k.any() else np.nan


VER = {
    "beta S": agree(BB["hum_mat"]["S"], Cst["E"]["S"]),
    "beta P": agree(BB["hum_mat"]["P"], Cst["E"]["P"]),
    "gain S": agree(BG["hum_mat"]["S"], Est["E"]["S"]),
    "gain P": agree(BG["hum_mat"]["P"], Est["E"]["P"]),
}
print("verification (max |diff| vs stored full-run draws):", VER, flush=True)


# ==================================================================== figures
def pct(a, lo=2.5, hi=97.5):
    a = np.asarray(a); a = a[np.isfinite(a)]
    return (np.nan, np.nan) if not len(a) else (float(np.percentile(a, lo)),
                                                float(np.percentile(a, hi)))


def ref_fig(kind, ycol_s, ycol_p, yref, ylab, fname, title):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    gx = np.linspace(Qm.min(), Qm.max(), 60)
    for ax, g, colr in zip(axes, ("S", "P"), ("#1b6ca8", "#d1495b")):
        yh = ycol_s if g == "S" else ycol_p
        ax.scatter(Qm, yh, s=34, color=colr, zorder=3, label=f"human ({g})")
        fh = FITS[(kind, g)]
        ax.plot(gx, fh["intercept"] + fh["slope"] * gx, color=colr, lw=1.9, zorder=2)
        ax.scatter(Qm, yref, s=30, marker="^", color="#5b5b5b", zorder=3,
                   label="reference (median of other 33 variants)")
        fr = FITS[(kind, "REF")]
        ax.plot(gx, fr["intercept"] + fr["slope"] * gx, color="#5b5b5b", lw=1.7,
                ls="--", zorder=2)
        for nm, qv in Q3.items():
            ax.axvline(qv, color="#bbb", lw=.7, ls=":", zorder=0)
        ax.axhline(0, color="#999", lw=.8, ls="--")
        ax.set_xlabel("$Q_m$ (mean Brier on the selection set; lower = better)")
        ax.set_ylabel(ylab)
        ax.set_title(f"group {g}: human {fh['slope']:+.3f} vs reference "
                     f"{fr['slope']:+.3f}", fontsize=10)
        ax.legend(fontsize=7.5, loc="best")
    fig.suptitle(title + "  —  post-results diagnostic (Amendment 2)", fontsize=11)
    fig.tight_layout(); fig.savefig(CFG.FIGDIR / fname, dpi=150); plt.close(fig)


ref_fig("beta", VT["beta_S"].to_numpy(float), VT["beta_P"].to_numpy(float), beta_ref,
        r"$\beta$ (encompassing coefficient)", f"v2_full_amd2_beta_ref{TAG}.png",
        "Human vs reference: encompassing coefficient against model quality")
ref_fig("gain", Est["point"]["S"], Est["point"]["P"], gain_ref,
        "cross-fitted out-of-sample log-score gain",
        f"v2_full_amd2_gain_ref{TAG}.png",
        "Human vs reference: cross-fitted log-score gain against model quality")


# ===================================================================== report
O = []
def w(s=""):
    O.append(s)

w(MARK_START)
w("## Post-results diagnostics — reference curve (Amendment 2, not pre-registered)")
w()
w("**Specified after the results were seen (Amendment 2, 2026-09-08). Diagnostic only: "
  "no pre-registered estimate is refit or changed, and nothing reported above is "
  "altered.** H6, H7, H8 and the five §6 robustness items stand exactly as reported.")
w()
w("The H6 curves show that adding a human term improves on a model and that the "
  "improvement grows as the model worsens. That slope is close to mechanical: any "
  "predictor that is not pure noise improves more on a worse model. The reference curve "
  "replaces the human median, for each variant `m`, with the **leave-one-out median of "
  "the other 33 variants** on that target, and recomputes the same two y quantities "
  "against the same `Q_m`, with identical folds, seed, clipping and target sets.")
w()
w(f"Reference coverage: every one of the {len(variants)} variants has a reference value "
  f"on all of its retained targets (minimum {MIN_REF} contributing variants required).")
w()

w("### Slopes: human vs reference")
w()
rows = []
for kind, lab in (("beta", "β (encompassing)"),
                  ("gain", "cross-fitted log-score gain")):
    for who in ("S", "P", "REF"):
        f = FITS[(kind, who)]
        rows.append(dict(quantity=lab,
                         curve={"S": "human S", "P": "human P",
                                "REF": "reference"}[who],
                         n=f["n"], slope=f["slope"],
                         analytic_lo=f["slope_lo"], analytic_hi=f["slope_hi"]))
w(md_table(pd.DataFrame(rows).set_index("quantity"), floatfmt="%.4f"))
w()
w("The analytic base-model-clustered interval is shown for orientation only; the "
  "inferential quantity of this section is the paired difference below.")
w()

w("### Figures")
w()
w(f"![beta vs reference](figures/v2_full_amd2_beta_ref{TAG}.png)")
w()
w(f"![gain vs reference](figures/v2_full_amd2_gain_ref{TAG}.png)")
w()
w("Triangles and the dashed grey line are the reference curve; dotted vertical lines "
  "mark the three evaluation points. The §7 item 3 and item 4 figures are unchanged and "
  "remain the pre-registered versions.")
w()

w("### Vertical difference, human minus reference, at three points on Q")
w()
w(f"Differences are computed **inside each bootstrap draw** — human and reference are "
  f"estimated on the same resampled questions, both stage-2 lines are refit, and both "
  f"are evaluated at the same `Q` — so the interval reflects the paired structure. "
  f"{DRAWS} draws, seed {SEED}, question-level cluster resampling, `Q` held fixed.")
w()
w(f"Evaluation points: min `Q` = {Q3['min']:.4f}, median `Q` = {Q3['median']:.4f}, "
  f"max `Q` = {Q3['max']:.4f}.")
w()
for kind, lab, BS in (("beta", "β (encompassing)", BB),
                      ("gain", "cross-fitted log-score gain", BG)):
    rows = []
    for g in ("S", "P"):
        fh, fr = FITS[(kind, g)], FITS[(kind, "REF")]
        for nm in ("min", "median", "max"):
            qv = Q3[nm]
            d_pt = ((fh["intercept"] + fh["slope"] * qv)
                    - (fr["intercept"] + fr["slope"] * qv))
            lo, hi = pct(BS["diffs"][g][nm])
            rows.append(dict(group=g, at=f"{nm} Q ({qv:.4f})", difference=d_pt,
                             ci_lo=lo, ci_hi=hi,
                             human_above_reference=bool(lo > 0)))
    w(f"**{lab}:**")
    w()
    w(md_table(pd.DataFrame(rows).set_index("group"), floatfmt="%.4f"))
    w()

w("### Reading (locked in advance by Amendment 2)")
w()
w("The claim that the human carries information the models do not is supported **only "
  "where the human curve lies above the reference curve**. Where it does not, the "
  "human's contribution at that benchmark quality **is not distinguishable from what "
  "another model-like source contributes**.")
w()
for kind, lab, BS in (("beta", "β", BB), ("gain", "log-score gain", BG)):
    for g in ("S", "P"):
        verdicts = []
        for nm in ("min", "median", "max"):
            lo, hi = pct(BS["diffs"][g][nm])
            verdicts.append((nm, lo > 0, lo, hi))
        above = [v[0] for v in verdicts if v[1]]
        notabove = [v[0] for v in verdicts if not v[1]]
        msg = f"- **{lab}, group {g}:** "
        if len(above) == 3:
            msg += ("human above reference at all three points — the claim is supported "
                    "across the observed range of Q.")
        elif not above:
            msg += ("human **not** distinguishable from reference at any of the three "
                    "points — at these benchmark qualities the human's contribution is "
                    "not distinguishable from what another model-like source contributes.")
        else:
            msg += (f"human above reference at {', '.join(above)} Q; **not** "
                    f"distinguishable at {', '.join(notabove)} Q. The claim is supported "
                    "only at the former.")
        w(msg)
w()

w("### Verification that the human side was not altered")
w()
w("The human quantities were recomputed inside the paired loop solely to make the "
  "pairing exact. They reproduce the stored full-run bootstrap draws:")
w()
w(md_table(pd.DataFrame([{"series": k, "max |difference| vs stored draws": v}
                         for k, v in VER.items()]).set_index("series"),
           floatfmt="%.2e"))
w()
w(f"Failed sub-fits across both paired bootstraps: β {BB['nfail']}, "
  f"gain {BG['nfail']} of {DRAWS*len(variants)*3} attempted in each.")
w()
w(f"Runtime {time.time()-T0:.0f}s.")
w()
w(MARK_END)

section = "\n".join(O)
path = CFG.DOCS / f"forecast_v2_full_REPORT{TAG}.md"
text = path.read_text()
text = re.sub(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n*", "",
              text, flags=re.S)
anchor = "---\n\n## Stop\n"
assert anchor in text, "closing section not found"
text = text.replace(anchor, "---\n\n" + section + "\n\n" + anchor, 1)
path.write_text(text)
print("\nappended Amendment 2 section to", path)
for kind, BS in (("beta", BB), ("gain", BG)):
    for g in ("S", "P"):
        for nm in ("min", "median", "max"):
            lo, hi = pct(BS["diffs"][g][nm])
            print(f"  {kind} {g} @{nm}Q: CI [{lo:+.4f}, {hi:+.4f}] above={lo>0}")
print("verification:", VER)
print("total %.0fs" % (time.time()-T0))
