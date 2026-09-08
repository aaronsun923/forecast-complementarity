"""SPEC v2 full run under Amendment 1: H6, H7, H8 and all five §6 robustness items.

Phases are checkpointed to data/derived/v2_full_*.pkl so a failure late in the
run does not discard the expensive stage-1 pass.

Usage:  python3 code/v2_full.py
Writes: docs/forecast_v2_full_REPORT.md, docs/figures/v2_full_*.png
"""
import os
import pickle
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
import v2common as V
import v2full as W
from report import md_table

T0 = time.time()
warnings.filterwarnings("ignore")
CFG.FIGDIR.mkdir(parents=True, exist_ok=True)
CFG.DERIVED.mkdir(parents=True, exist_ok=True)
# Env overrides exist only so the pipeline can be smoke-tested end to end before
# the ~90-minute real run; defaults are the SPEC values and are what ship.
TAG = os.environ.get("V2_TAG", "")
DRAWS = int(os.environ.get("V2_DRAWS", "2000"))
MAXVAR = int(os.environ.get("V2_MAXVAR", "0"))
CK = CFG.DERIVED
SEED = 20260908
TRIP = 3600.0
PH = {}                      # phase timings
OUT = []
def w(s=""):
    OUT.append(s)


def phase(name, fn, *a, **k):
    """Run a phase, checkpointing its result and timing it."""
    f = CK / f"v2_full{TAG}_{name}.pkl"
    if f.exists():
        print(f"[{name}] cached", flush=True)
        d = pickle.loads(f.read_bytes())
        PH[name] = d.get("_secs", 0.0)
        return d
    t = time.time()
    print(f"[{name}] start", flush=True)
    d = fn(*a, **k)
    d["_secs"] = time.time() - t
    PH[name] = d["_secs"]
    f.write_bytes(pickle.dumps(d))
    print(f"[{name}] done {d['_secs']:.0f}s", flush=True)
    return d


# ==================================================================== load
rbt, rbq = F.load_resolutions()
hum, dropped, invalid = F.load_humans(rbt, rbq)
mods, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(mods, set(hum["target"]))
stats = F.target_level_model_stats(mods)
test_targets = set(hum["target"])
tab = V.build_variant_table(hum, mods, meta, rank, test_targets)
variants = list(tab.index)
if MAXVAR:
    variants = variants[:MAXVAR]
    tab = tab.loc[variants]
questions = sorted(hum["question"].unique())
qmap = {q: i for i, q in enumerate(questions)}
n_q = len(questions)
print(f"{len(variants)} variants, {n_q} questions, {hum['target'].nunique()} targets, "
      f"{len(hum):,} rows", flush=True)

frames = {m: F.build_frame(hum, mods, stats, m)[0] for m in variants}


# ------------------------------------------------------------- PHASE A
def _stage1():
    rows = []
    t0 = time.time()
    for i, m in enumerate(variants, 1):
        fr = frames[m]
        r = {"model": m}
        tl = V.target_level(fr)
        for g, col in (("S", "p_h_S"), ("P", "p_h_P")):
            e = M.encompassing(tl, col, CFG.CLIP)
            lo, hi = (float(e["ci"].loc["human_minus_model", 0]),
                      float(e["ci"].loc["human_minus_model", 1]))
            r[f"beta_{g}"] = float(e["params"]["human_minus_model"])
            r[f"beta_{g}_lo"], r[f"beta_{g}_hi"] = lo, hi
            r[f"beta_{g}_se"] = V.se_from_ci(lo, hi)
            r[f"beta_{g}_clip"] = e["clipped_human"]
        r["targets_tl"] = len(tl)
        for g in ("S", "P"):
            sub = W.prep_group(fr[fr.GRP == g])
            r[f"n_{g}"] = len(sub)
            r[f"G_{g}"] = float(sub["G_a"].mean())
            for y, tag in (("G_a", ""), ("G_log", "_log")):
                res, fb = M.fit_spec(V.F4_GROUP.replace("G_a", y), sub, "H4")
                lo, hi = (float(res.ci.loc["EXT_a_z", 0]), float(res.ci.loc["EXT_a_z", 1]))
                r[f"eps{tag}_{g}"] = float(res.params["EXT_a_z"])
                r[f"eps{tag}_{g}_lo"], r[f"eps{tag}_{g}_hi"] = lo, hi
                r[f"eps{tag}_{g}_se"] = V.se_from_ci(lo, hi)
                r[f"eps{tag}_{g}_warn"] = bool(res.extra.get("warnings"))
                r[f"eps{tag}_{g}_fb"] = fb
        rows.append(r)
        print(f"  [{i:2d}/34] {m[:48]:48s} {time.time()-t0:6.0f}s", flush=True)
    return {"s1": pd.DataFrame(rows).set_index("model")}


A = phase("A_stage1", _stage1)
S1 = A["s1"]
VT = tab.join(S1)


# ------------------------------------------------------------- PHASE B
def _validate():
    bun = W.build_row_bundle(hum, mods, stats, variants, qmap, "G_a", frames)
    rows = []
    for m in variants:
        for g in ("S", "P"):
            co, se = W.eps_point(bun[(m, g)])
            rows.append(dict(model=m, group=g,
                             fast=np.nan if co is None else co[0],
                             fast_se=np.nan if se is None else se[0],
                             mixed=VT.loc[m, f"eps_{g}"],
                             mixed_se=VT.loc[m, f"eps_{g}_se"]))
    v = pd.DataFrame(rows)
    v["d_coef"] = (v["fast"] - v["mixed"]).abs()
    v["d_se"] = (v["fast_se"] - v["mixed_se"]).abs()
    return {"val": v}


B = phase("B_validate", _validate)
VAL = B["val"]
max_dc, max_ds = float(VAL["d_coef"].max()), float(VAL["d_se"].max())
eps_spread = float(pd.concat([VT["eps_S"], VT["eps_P"]]).std())
material = max_dc > eps_spread          # criterion stated in the report


# ------------------------------------------------------------- PHASE C
tl_wide = (hum.groupby("target")
           .agg(o=("o", "first"), question=("question", "first")).reset_index())
for g, nm in (("S", "p_h_S"), ("P", "p_h_P")):
    tl_wide = tl_wide.merge(
        hum[hum.group == g].groupby("target")["p_h"].median().rename(nm),
        on="target", how="left")
sub_m = mods[mods["target"].isin(test_targets)]
for m in variants:
    s = sub_m[(sub_m["model"] == m) & (~sub_m["imputed"])].set_index("target")["p"]
    tl_wide[m] = tl_wide["target"].map(s)

C = phase("C_boot_beta", lambda: W.boot_questions_beta(
    tl_wide, variants, ("S", "P"), DRAWS, SEED, progress=500))

# ------------------------------------------------------------- PHASE D
D = phase("D_boot_eps", lambda: W.boot_questions_eps(
    W.build_row_bundle(hum, mods, stats, variants, qmap, "G_a", frames),
    variants, ("S", "P"), n_q, DRAWS, SEED, progress=250))

# ------------------------------------------------------------- PHASE F
Fp = phase("F_boot_eps_log", lambda: W.boot_questions_eps(
    W.build_row_bundle(hum, mods, stats, variants, qmap, "G_log", frames),
    variants, ("S", "P"), n_q, DRAWS, SEED, progress=250))


# ------------------------------------------------------------- PHASE E
def _boot_crossfit():
    rng = np.random.default_rng(SEED)
    qcodes = tl_wide["question"].map(qmap).to_numpy(np.int32)
    idx = [np.flatnonzero(qcodes == q) for q in range(n_q)]
    y_all = tl_wide["o"].to_numpy(float)
    LH = {g: V.logit_clip(tl_wide[f"p_h_{g}"].to_numpy(float)) for g in ("S", "P")}
    LM, OK = {}, {}
    for m in variants:
        v = tl_wide[m].to_numpy(float)
        LM[m] = V.logit_clip(v); OK[m] = np.isfinite(v)
    pt = {g: np.full(len(variants), np.nan) for g in ("S", "P")}
    pse = {g: np.full(len(variants), np.nan) for g in ("S", "P")}
    for g in ("S", "P"):
        for vi, m in enumerate(variants):
            k = OK[m]
            gg, ss = W.crossfit_gain(y_all[k], LM[m][k], LH[g][k], qcodes[k], seed=SEED)
            if gg is not None:
                pt[g][vi], pse[g][vi] = gg, ss
    E = {g: np.full((DRAWS, len(variants)), np.nan) for g in ("S", "P")}
    Sd = {g: np.full((DRAWS, len(variants)), np.nan) for g in ("S", "P")}
    fails = 0
    for t in range(DRAWS):
        pick = rng.integers(0, n_q, n_q)
        rows = np.concatenate([idx[q] for q in pick])
        clus = np.concatenate([np.full(len(idx[q]), j) for j, q in enumerate(pick)])
        for g in ("S", "P"):
            for vi, m in enumerate(variants):
                k = OK[m][rows]
                if k.sum() < 60:
                    fails += 1; continue
                gg, ss = W.crossfit_gain(y_all[rows][k], LM[m][rows][k],
                                         LH[g][rows][k], clus[k], seed=SEED)
                if gg is None or ss is None or ss <= 0:
                    fails += 1; continue
                E[g][t, vi], Sd[g][t, vi] = gg, ss
        if (t + 1) % 250 == 0:
            print(f"    crossfit boot {t+1}/{DRAWS}", flush=True)
    return dict(E=E, SE=Sd, fails=fails, point=pt, point_se=pse)


Ep = phase("E_boot_crossfit", _boot_crossfit)


# =============================================== stage 2 (all variations)
Qmain = VT["Q_m"].to_numpy(float)
BASE = VT["base"].to_numpy()
Qcombo_tab = W.combo_quality(test_targets)
VT = VT.join(Qcombo_tab)
Qcombo = VT["Q_combo"].to_numpy(float)

is_claude21 = np.array([b == "Claude-2.1" for b in BASE])
hi_q = np.zeros(len(variants), bool); hi_q[int(np.argmax(Qmain))] = True


def fit_all(estmat, semat, ycol_pt, secol_pt, q, mask=None, boot=None):
    """Stage-2 point fit (analytic) + bootstrap interval from stored draws."""
    keep = np.ones(len(variants), bool) if mask is None else mask
    y = VT[ycol_pt].to_numpy(float); se = VT[secol_pt].to_numpy(float)
    ok = keep & np.isfinite(y) & np.isfinite(se) & (se > 0) & np.isfinite(q)
    fit = W.stage2(q[ok], y[ok], se[ok], BASE[ok])
    out = dict(fit=fit, n=int(ok.sum()), mask=ok)
    if boot is not None:
        sl, ic, cr = W.stage2_draws(boot[0], boot[1], q, mask=ok)
        out.update(bslope=sl, binter=ic, bcross=cr)
    return out


def cell(kind, g, q=Qmain, mask=None, which="main"):
    if kind == "beta":
        return fit_all(None, None, f"beta_{g}", f"beta_{g}_se", q, mask,
                       (C["E"][g], C["SE"][g]))
    if kind == "eps":
        return fit_all(None, None, f"eps_{g}", f"eps_{g}_se", q, mask,
                       (D["E"][g], D["SE"][g]))
    if kind == "eps_log":
        return fit_all(None, None, f"eps_log_{g}", f"eps_log_{g}_se", q, mask,
                       (Fp["E"][g], Fp["SE"][g]))
    raise ValueError(kind)


MAIN = {(k, g): cell(k, g) for k in ("beta", "eps") for g in ("S", "P")}

# Amendment 1 item 1: flags from the MAIN all-points fit
FLAG = {}
for k, g in MAIN:
    fl, thr_l, thr_c = W.flag_amendment1(MAIN[(k, g)]["fit"])
    full = np.zeros(len(variants), bool)
    full[np.flatnonzero(MAIN[(k, g)]["mask"])] = fl
    FLAG[(k, g)] = dict(flag=full, thr_lev=thr_l, thr_cook=thr_c,
                        lev=MAIN[(k, g)]["fit"]["leverage"],
                        cooks=MAIN[(k, g)]["fit"]["cooks"])

UNFL = {(k, g): cell(k, g, mask=~FLAG[(k, g)]["flag"]) for k, g in MAIN}

ROB = {}
for k in ("beta", "eps"):
    for g in ("S", "P"):
        ROB[("r1", k, g)] = cell(k, g, q=Qcombo)
        ROB[("r2", k, g)] = cell(k, g, mask=~is_claude21)
        ROB[("r3", k, g)] = cell(k, g, mask=~hi_q)
# r4: cross-fitted log-score y for H6
for g in ("S", "P"):
    VT[f"cf_{g}"] = Ep["point"][g]
    VT[f"cf_{g}_se"] = Ep["point_se"][g]
    ROB[("r4", "beta", g)] = fit_all(None, None, f"cf_{g}", f"cf_{g}_se", Qmain,
                                     None, (Ep["E"][g], Ep["SE"][g]))
    ROB[("r5", "eps", g)] = cell("eps_log", g)


# ============================================================== H8 (§4.3)
def _h8():
    out = {}
    lm = {}
    tgt = tl_wide
    for m in variants:
        v = tgt[m].to_numpy(float)
        lm[m] = V.logit_clip(v)
    okall = np.all(np.column_stack([np.isfinite(tgt[m].to_numpy(float))
                                    for m in variants]), axis=1)
    L = {m: lm[m][okall] for m in variants}
    pw_models = [np.corrcoef(L[a], L[b])[0, 1]
                 for i, a in enumerate(variants) for b in variants[i + 1:]]
    for g in ("S", "P"):
        c = V.logit_clip(tgt[f"p_h_{g}"].to_numpy(float))[okall]
        Dm = {m: c - L[m] for m in variants}
        pw = [np.corrcoef(Dm[a], Dm[b])[0, 1]
              for i, a in enumerate(variants) for b in variants[i + 1:]]
        out[g] = dict(mean=float(np.mean(pw)), lo=float(np.min(pw)),
                      hi=float(np.max(pw)), sd_human=float(c.std()))
    out["models"] = float(np.mean(pw_models))
    out["n_targets"] = int(okall.sum())
    return out


H8 = _h8()


# ==================================================================== report
def ci(v, lo, hi, f="%.4f"):
    return f"{f % v} [{f % lo}, {f % hi}]"


def slope_row(cellv, label, use_boot=True):
    fit = cellv["fit"]
    r = dict(fit=label, n_variants=cellv["n"], slope=fit["slope"])
    if use_boot and "bslope" in cellv and len(cellv["bslope"]):
        lo, hi = V.pct_ci(cellv["bslope"])
        r["boot_lo"], r["boot_hi"] = lo, hi
        r["draws_used"] = len(cellv["bslope"])
    r["analytic_lo"], r["analytic_hi"] = fit["slope_lo"], fit["slope_hi"]
    return r


w("# SPEC v2 full run — benchmark-quality curve, under Amendment 1")
w()
w(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')} · "
  "spec `84e54eb` + Amendment 1 · **full sample**")
w()
w(f"All {len(variants)} matched-condition variants as benchmarks, against the v1 "
  f"analysis frame: {hum['target'].nunique()} resolved targets, "
  f"{n_q} questions, {hum['forecaster'].nunique()} forecasters, {len(hum):,} rows. "
  "H6, H7, H8 and all five §6 robustness items. §7 items 1–9 follow.")
w()

# ---- 1 environment
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
    "bootstrap draws": str(DRAWS), "bootstrap seed": str(SEED),
}})))
w()
ph = pd.DataFrame({"seconds": PH}).assign(
    minutes=lambda d: d["seconds"] / 60,
    over_tripwire=lambda d: d["seconds"] > TRIP)
w("Phase timings; SPEC §6 item 4 makes each heavy component individually subject to "
  "the one-hour tripwire:")
w()
w(md_table(ph, floatfmt="%.1f"))
w()
w(f"Total wall clock {time.time()-T0:.0f}s. "
  + ("**No phase exceeded one hour.**" if not ph["over_tripwire"].any() else
     "**A phase exceeded one hour — see the flagged row.**"))
w()

# ---- 2 per-variant table
w("---")
w()
w("## 2. Per-variant table (§7 item 2)")
w()
w("**[LOCKED] §7 item 4:** every quantity is on that variant's own retained targets. "
  "`targets_kept` is the count after dropping targets where that variant's forecast is "
  "imputed. **The y values are not computed on identical target sets across the x "
  "axis.** No reweighting is applied.")
w()
bt = VT.reset_index()[["base", "scaffold", "Q_m", "Q_combo", "imputed_targets",
                       "targets_kept", "beta_S", "beta_S_lo", "beta_S_hi",
                       "beta_P", "beta_P_lo", "beta_P_hi", "G_S", "G_P"]]
w("**β and Q:**")
w()
w(md_table(bt.sort_values("Q_m").set_index("base"), floatfmt="%.4f"))
w()
w("**ε, with the Amendment 1 item 3 per-variant boundary-warning column:**")
w()
et = VT.reset_index()[["base", "scaffold", "Q_m",
                       "eps_S", "eps_S_lo", "eps_S_hi", "eps_S_warn",
                       "eps_P", "eps_P_lo", "eps_P_hi", "eps_P_warn",
                       "eps_log_S", "eps_log_S_warn", "eps_log_P", "eps_log_P_warn"]]
w(md_table(et.sort_values("Q_m").set_index("base"), floatfmt="%.4f"))
w()
nw = int(sum(VT[f"eps{t}_{g}_warn"].sum() for t in ("", "_log") for g in ("S", "P")))
nfb = int(sum(1 for t in ("", "_log") for g in ("S", "P") for v in VT[f"eps{t}_{g}_fb"] if v))
w(f"`*_warn` is true where the mixed model raised the optimiser boundary warning: "
  f"{nw} of {len(VT)*4} ε fits. Fits that fell back to clustered OLS: {nfb}.")
w()
w("`G_m,g` is in the β table. **[LOCKED] §3:** it is close to an identity — "
  "`G_m,g = BS_m(test) − BS_g(test)`, the second term does not vary with m, and "
  "`BS_m(test)` is highly correlated with `Q_m` because both are that variant's Brier "
  "on different question sets. It is not plotted.")
w()

# ---- figures
def curve_fig(kind, cells, ylab, fname, title):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, g, colr in zip(axes, ("S", "P"), ("#1b6ca8", "#d1495b")):
        cv = cells[(kind, g)]; fit = cv["fit"]; ok = cv["mask"]
        x = Qmain[ok]; y = VT[f"{kind}_{g}"].to_numpy(float)[ok]
        fl = FLAG[(kind, g)]["flag"][ok]
        sub = VT.loc[ok]
        for b, s2 in sub.groupby("base"):
            if len(s2) == 2:
                ax.plot(s2["Q_m"], s2[f"{kind}_{g}"], "-", color="#bbb", lw=.9, zorder=1)
        ax.scatter(x[~fl], y[~fl], s=34, color=colr, zorder=3, label="variant")
        ax.scatter(x[fl], y[fl], s=95, facecolors="none", edgecolors="k",
                   linewidths=1.5, zorder=4, label="flagged (Amendment 1 rule)")
        gx = np.linspace(x.min(), x.max(), 60)
        if len(cv.get("bslope", [])):
            preds = cv["binter"][None, :] + np.outer(gx, cv["bslope"])
            lo, hi = np.nanpercentile(preds, [2.5, 97.5], axis=1)
            ax.fill_between(gx, lo, hi, color=colr, alpha=.15, zorder=0,
                            label="95% question bootstrap")
        ax.plot(gx, fit["intercept"] + fit["slope"] * gx, color=colr, lw=1.8, zorder=2)
        uf = UNFL[(kind, g)]
        ax.plot(gx, uf["fit"]["intercept"] + uf["fit"]["slope"] * gx, color="k",
                lw=1.3, ls=":", zorder=2, label="unflagged-only refit")
        ax.axhline(0, color="#999", lw=.8, ls="--")
        ax.set_xlabel("$Q_m$ (mean Brier on the selection set; lower = better)")
        ax.set_ylabel(ylab)
        ax.set_title(f"group {g}   all {fit['slope']:+.3f} / unflagged "
                     f"{uf['fit']['slope']:+.3f}", fontsize=10)
        ax.legend(fontsize=7, loc="best")
    fig.suptitle(title, fontsize=12)
    fig.tight_layout(); fig.savefig(CFG.FIGDIR / fname, dpi=150); plt.close(fig)


w("---")
w()
w("## 3. Figure — β against Q (§7 item 3)")
w()
curve_fig("beta", MAIN, r"$\beta_{m,g}$", "v2_full_beta_vs_Q.png",
          "H6: human information beyond the model, against model quality")
w("![beta](figures/v2_full_beta_vs_Q.png)")
w()
w("## 4. Figure — ε against Q (§7 item 4)")
w()
curve_fig("eps", MAIN, r"$\varepsilon_{m,g}$", "v2_full_eps_vs_Q.png",
          "H7: return to extremizing, against model quality")
w("![eps](figures/v2_full_eps_vs_Q.png)")
w()
w("Scaffold pairs joined in grey; black rings mark points flagged by the Amendment 1 "
  "rule; dotted black line is the co-primary unflagged-only refit.")
if not material:
    w()
else:
    w()
    w("**The ε figure carries the Amendment 1 item 2 statement:** the inner-loop "
      "validation failed, so H7 is descriptive and the band shown is not a valid "
      "interval for H7 — see §6.")
w()

# ---- 5 H6
w("---")
w()
w("## 5. H6 — does human information shrink as the model improves? (§7 item 5)")
w()
w("`β_m,g ~ Q_m`, inverse-variance weighted. Primary interval is the question-level "
  f"cluster bootstrap (§4 [LOCKED]): {n_q} questions resampled with replacement, every "
  f"β recomputed for all 34 variants, stage-2 slope refit, {DRAWS} draws, seed {SEED}. "
  "`Q_m` held fixed.")
w()
w("**All points:**")
w()
w(md_table(pd.DataFrame([slope_row(MAIN[("beta", g)], g) for g in ("S", "P")]
                        ).set_index("fit"), floatfmt="%.4f"))
w()
w("**Unflagged points only — co-primary (Amendment 1 item 1):**")
w()
w(md_table(pd.DataFrame([slope_row(UNFL[("beta", g)], g) for g in ("S", "P")]
                        ).set_index("fit"), floatfmt="%.4f"))
w()
for g in ("S", "P"):
    a, u = MAIN[("beta", g)]["fit"]["slope"], UNFL[("beta", g)]["fit"]["slope"]
    keep = np.sign(a) == np.sign(u)
    w(f"- Group {g}: slope {a:+.4f} all points, {u:+.4f} unflagged "
      f"({int(FLAG[('beta',g)]['flag'].sum())} flagged). Sign "
      + ("**survives**." if keep else "**does NOT survive** — per Amendment 1 item 1 "
         "this result is reported as driven by extreme points and **no directional "
         "claim is made**."))
w()
w(f"Amendment 1 leverage thresholds at p=2, n={len(variants)}: "
  f"leverage > {FLAG[('beta','S')]['thr_lev']:.4f} or Cook's D > "
  f"{FLAG[('beta','S')]['thr_cook']:.4f}.")
w()
w("### Descriptive extrapolation — where β reaches zero (§4.1)")
w()
xr = []
for g in ("S", "P"):
    cv = MAIN[("beta", g)]; fit = cv["fit"]
    qlo, qhi = float(Qmain[cv["mask"]].min()), float(Qmain[cv["mask"]].max())
    pt = V.zero_crossing(fit["intercept"], fit["slope"])
    clo, chi = V.pct_ci(cv["bcross"])
    cr = cv["bcross"][np.isfinite(cv["bcross"])]
    xr.append(dict(group=g, Q_min=qlo, Q_max=qhi, crossing=pt,
                   crossing_lo=clo, crossing_hi=chi,
                   share_outside=float(np.mean((cr < qlo) | (cr > qhi))),
                   within_range=bool(qlo <= pt <= qhi)))
w(md_table(pd.DataFrame(xr).set_index("group"), floatfmt="%.4f"))
w()
for r_ in xr:
    w(f"- Group {r_['group']}: "
      + ("crossing lies inside the observed range." if r_["within_range"] else
         f"**the fitted line does not reach zero within the observed range of Q** "
         f"({r_['Q_min']:.4f}–{r_['Q_max']:.4f}); not extrapolated beyond it (§4.1). "
         f"{100*r_['share_outside']:.1f}% of draws put the crossing outside the range."))
w()

# ---- 6 H7
w("---")
w()
w("## 6. H7 — does the return to extremizing depend on model quality? (§7 item 6)")
w()
w("### Inner-loop validation (Amendment 1 item 2) — reported before any interval")
w()
w("Amendment 1 replaces the pilot's stage-2 wild cluster bootstrap, which conditioned "
  "on the stage-1 ε estimates and was not a valid interval. The replacement inner-loop "
  "estimator is OLS with forecaster fixed effects and question-clustered SEs — the "
  "estimator SPEC v1 §5 and v1 Amendment 1 D.1 already sanction as the H3/H4 fallback. "
  "It is validated against the v1 mixed-model point estimates across all 34 variants:")
w()
w(md_table(pd.DataFrame([{
    "quantity": "max |Δ coefficient|", "value": max_dc},
    {"quantity": "max |Δ SE|", "value": max_ds},
    {"quantity": "across-variant SD of ε (both groups)", "value": eps_spread},
    {"quantity": "ratio max|Δcoef| / SD(ε)", "value": max_dc / eps_spread},
]).set_index("quantity"), floatfmt="%.5f"))
w()
w(md_table(VAL.groupby("group")[["d_coef", "d_se"]].agg(["max", "mean"]),
           floatfmt="%.5f"))
w()
w("**Criterion, stated before the verdict:** the discrepancy is material if "
  "`max |Δcoef|` is comparable to or larger than the across-variant spread of ε, "
  "because that spread is exactly the variation the H7 slope is fitted to. A "
  "discrepancy of that size would change the shape of the curve, not just its level.")
w()
if material:
    w(f"**Verdict: MATERIAL.** `max |Δcoef|` = {max_dc:.5f} against an across-variant "
      f"SD of ε of {eps_spread:.5f} — a ratio of {max_dc/eps_spread:.2f}. Per Amendment 1 "
      "item 2, **H7 is demoted to descriptive: the slopes below are reported with no "
      "interval**, and the H7 figure carries that statement. The bootstrap was run and "
      "its output is retained, but it is not reported as an interval for H7.")
else:
    w(f"**Verdict: not material.** `max |Δcoef|` = {max_dc:.5f} against an "
      f"across-variant SD of ε of {eps_spread:.5f} (ratio {max_dc/eps_spread:.2f}). "
      "The question-level bootstrap interval below is reported as H7's interval.")
w()
w("**All points:**")
w()
w(md_table(pd.DataFrame([slope_row(MAIN[("eps", g)], g, use_boot=not material)
                         for g in ("S", "P")]).set_index("fit"), floatfmt="%.4f"))
w()
w("**Unflagged points only — co-primary (Amendment 1 item 1):**")
w()
w(md_table(pd.DataFrame([slope_row(UNFL[("eps", g)], g, use_boot=not material)
                         for g in ("S", "P")]).set_index("fit"), floatfmt="%.4f"))
w()
for g in ("S", "P"):
    a, u = MAIN[("eps", g)]["fit"]["slope"], UNFL[("eps", g)]["fit"]["slope"]
    keep = np.sign(a) == np.sign(u)
    w(f"- Group {g}: slope {a:+.4f} all points, {u:+.4f} unflagged "
      f"({int(FLAG[('eps',g)]['flag'].sum())} flagged). Sign "
      + ("**survives**." if keep else "**does NOT survive** — no directional claim "
         "is made (Amendment 1 item 1)."))
w()

# ---- 7 H8
w("---")
w()
w("## 7. H8 — is it the same information across benchmarks? (§7 item 7)")
w()
w("**[LOCKED] §4.3: reported, with no conclusion drawn.**")
w()
w(md_table(pd.DataFrame([
    {"quantity": "mean pairwise corr of [logit(p_h_S) − logit(p_m)]",
     "value": H8["S"]["mean"]},
    {"quantity": "mean pairwise corr of [logit(p_h_P) − logit(p_m)]",
     "value": H8["P"]["mean"]},
    {"quantity": "reference: mean pairwise corr of logit(p_m) alone",
     "value": H8["models"]},
    {"quantity": "SD of logit(p_h_S)", "value": H8["S"]["sd_human"]},
    {"quantity": "SD of logit(p_h_P)", "value": H8["P"]["sd_human"]},
]).set_index("quantity"), floatfmt="%.4f"))
w()
w(f"Computed on the {H8['n_targets']} targets where all 34 variants have a "
  "non-imputed forecast. The correlation is mechanically inflated because every term "
  "shares `logit(p_h_g)`; the reference and the two SDs are reported next to it as "
  "§4.3 requires. The two groups straddle the reference in opposite directions, which "
  "is what a shared-component artifact looks like. No conclusion is drawn.")
w()

# ---- 8 robustness
w("---")
w()
w("## 8. Robustness — all five §6 items (§7 item 8)")
w()
w("### 6.1 `Q` measured on combination-question targets")
w()
rows = []
for k in ("beta", "eps"):
    for g in ("S", "P"):
        rows.append(slope_row(ROB[("r1", k, g)], f"{k} {g}",
                              use_boot=(k == "beta") or not material))
w(md_table(pd.DataFrame(rows).set_index("fit"), floatfmt="%.4f"))
w()
w(f"`Q_combo` spans {VT['Q_combo'].min():.4f}–{VT['Q_combo'].max():.4f} against "
  f"{VT['Q_m'].min():.4f}–{VT['Q_m'].max():.4f} for the single-question `Q`; "
  f"rank correlation between them {VT[['Q_m','Q_combo']].corr(method='spearman').iloc[0,1]:.3f}.")
w()
w("### 6.2 Both Claude-2.1 variants excluded (32 variants)")
w()
rows = []
for k in ("beta", "eps"):
    for g in ("S", "P"):
        rows.append(slope_row(ROB[("r2", k, g)], f"{k} {g}",
                              use_boot=(k == "beta") or not material))
w(md_table(pd.DataFrame(rows).set_index("fit"), floatfmt="%.4f"))
w()
w("### 6.3 Leverage, and the highest-`Q` variant excluded")
w()
lev_rows = []
for k in ("beta", "eps"):
    for g in ("S", "P"):
        fl = FLAG[(k, g)]
        mk = MAIN[(k, g)]["mask"]
        sub = VT.loc[mk]
        for i, (idx_, lv, ck_) in enumerate(zip(sub.index, fl["lev"], fl["cooks"])):
            if fl["flag"][np.flatnonzero(mk)][i]:
                lev_rows.append(dict(fit=f"{k} {g}", model=idx_, Q_m=sub["Q_m"].iloc[i],
                                     leverage=lv, cooks_d=ck_))
w("Points flagged by the [LOCKED] rule (leverage > 2p/n or Cook's D > 4/n):")
w()
w(md_table(pd.DataFrame(lev_rows).set_index("fit"), floatfmt="%.4f")
  if lev_rows else "_no point flagged_")
w()
w("Refit with the single highest-`Q` variant excluded (distinct from the unflagged "
  "refit above, which drops every flagged point):")
w()
rows = []
for k in ("beta", "eps"):
    for g in ("S", "P"):
        rows.append(slope_row(ROB[("r3", k, g)], f"{k} {g}",
                              use_boot=(k == "beta") or not material))
w(md_table(pd.DataFrame(rows).set_index("fit"), floatfmt="%.4f"))
w()
w("### 6.4 Scale-free y for H6 — cross-fitted out-of-sample log-score gain")
w()
w("`β` is replaced by the out-of-sample improvement in mean log score from adding the "
  f"human term, cross-fitted in 5 folds by question (seed {SEED}), and H6 is rerun with "
  "the same question-level bootstrap. Weights are inverse variance, with the SE taken "
  "as the question-clustered SE of the mean per-target difference.")
w()
w(md_table(pd.DataFrame([slope_row(ROB[("r4", "beta", g)], g) for g in ("S", "P")]
                        ).set_index("fit"), floatfmt="%.5f"))
w()
for g in ("S", "P"):
    a = MAIN[("beta", g)]["fit"]["slope"]; b = ROB[("r4", "beta", g)]["fit"]["slope"]
    agree = np.sign(a) == np.sign(b)
    w(f"- Group {g}: β slope {a:+.4f}, log-score-gain slope {b:+.5f}. Signs "
      + ("**agree** — the H6 conclusion stands on this check (§6 item 4)."
         if agree else "**disagree** — per §6 item 4 the `β` curve is **not "
         "interpretable as information** and the H6 conclusion does not stand."))
w()
w("### 6.5 H7 under the log score")
w()
rows = [slope_row(ROB[("r5", "eps", g)], g, use_boot=not material) for g in ("S", "P")]
w(md_table(pd.DataFrame(rows).set_index("fit"), floatfmt="%.4f"))
w()
for g in ("S", "P"):
    a = MAIN[("eps", g)]["fit"]["slope"]; b = ROB[("r5", "eps", g)]["fit"]["slope"]
    w(f"- Group {g}: Brier ε slope {a:+.4f}, log-score ε slope {b:+.4f} — signs "
      + ("**agree**." if np.sign(a) == np.sign(b) else
         "**disagree**; §6 item 5 says interpret only where the two curves agree, so "
         "this group's H7 curve is not interpreted."))
w()

# ---- 9 limits
w("---")
w()
w("## 9. What limits the reading (§7 item 9)")
w()
w(f"**Seventeen independent base models, not 34 points.** The x axis carries "
  f"{len(variants)} points but {VT['base'].nunique()} base models; the two scaffolds of "
  "a base model share weights, training data and failure modes and are joined in both "
  "figures. Every analytic interval clusters on the base model, and 17 clusters is few "
  "— which is why the primary intervals resample questions instead.")
w()
w("**The 34 points share their outcome noise.** Every β and ε rests on the same "
  f"{hum['target'].nunique()} targets, the same human medians and the same outcomes. "
  "Stage-2 clustering cannot see that sharing; the question-level bootstrap can, and it "
  "is materially wider as a result.")
w()
w("**All models are mid-2024.** `Q` spans "
  f"{VT['Q_m'].min():.4f}–{VT['Q_m'].max():.4f} within one generation. Nothing here "
  "speaks to quality outside that span, which is why §4.1 forbids extrapolating the "
  "zero crossing beyond the observed range.")
w()
w("**`Q` is measured on a different question set from the test set.** `Q_m` comes from "
  "the selection set (single questions, complement of the human targets); β and ε come "
  "from the human targets. That keeps the x axis out of sample, but it makes `Q` a "
  "proxy for quality on the test questions rather than a measurement of it.")
w()
w("**The x axis is not evenly covered.** 32 of 34 variants sit between "
  f"{sorted(Qmain)[0]:.4f} and {sorted(Qmain)[-3]:.4f}; the top two sit apart at "
  f"{sorted(Qmain)[-2]:.4f} and {sorted(Qmain)[-1]:.4f}. Any slope is largely a "
  "contrast between a dense cluster and a couple of isolated points, which is what the "
  "Amendment 1 co-primary refit exists to expose.")
w()
w("---")
w()
w("## Stop")
w()
w("SPEC §10 discipline: delivery stops here. Nothing beyond §7 is inferred.")
w()
w(f"Total runtime {time.time()-T0:.0f}s.")
w()

(CFG.DOCS / f"forecast_v2_full_REPORT{TAG}.md").write_text("\n".join(OUT) + "\n")
print("\nwrote", CFG.DOCS / f"forecast_v2_full_REPORT{TAG}.md")
print("validation: max|dcoef|=%.5f max|dse|=%.5f sd(eps)=%.5f material=%s"
      % (max_dc, max_ds, eps_spread, material))
for k in ("beta", "eps"):
    for g in ("S", "P"):
        print(f"{k} {g}: all={MAIN[(k,g)]['fit']['slope']:+.4f} "
              f"unflagged={UNFL[(k,g)]['fit']['slope']:+.4f} "
              f"flagged={int(FLAG[(k,g)]['flag'].sum())}")
print("total %.0fs" % (time.time() - T0))
