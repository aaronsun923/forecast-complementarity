"""SPEC v3 Amendment 6: out-of-sample combination.

The locked v1 and v2 paths are not touched. The frame is rebuilt with the v1
fbdata calls; the target-level table is v2common.target_level; Mens mirrors
the v2 Amendment 2 leave-one-out reference (median of the 33 matched variants
other than M1, at least 10 contributing); the folds are the v2 cross-fit
folds (v2full.crossfit_gain: seed 20260908, permutation of the sorted question
codes, fold = rank mod 5), checked at run time by reproducing the stored v2
cross-fitted gain for M1 exactly.

Usage:  python3 code/amendment6.py
Writes: docs/amendment6_REPORT.md
"""
import os
import pickle
import subprocess
import sys
import time
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

import config as CFG
import fbdata as F
import models as M
import v2common as V
import v2full as W
from report import md_table

warnings.filterwarnings("ignore")
T0 = time.time()

SPEC_COMMIT = "751e0fb68d0d8131044cea92b88375bdf865c499"
LOCKED = {"S": (1.79, 1.04, 2.53), "P": (0.97, 0.24, 1.70)}
MNEWS = "Claude-3-5-Sonnet-20240620 (superforecaster with news 1)"
FOLD_SEED = 20260908          # v2 cross-fit folds (v2full.crossfit_gain default)
N_FOLDS = 5
SEED = 20260906               # SPEC v3: bootstrap and noise control
DRAWS = int(os.environ.get("A6_DRAWS", "2000"))   # env override for smoke tests only
NOISE_DRAWS = int(os.environ.get("A6_NOISE", "200"))
NOISE_K = 7
MIN_REF = 10                  # v2 Amendment 2
SD_RULE = 0.2
LO, HI = CFG.CLIP

OUT = []
def w(s=""):
    OUT.append(s)


# ===================================================================== load
rbt, rbq = F.load_resolutions()
humans, _, _ = F.load_humans(rbt, rbq)
mods, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(mods, set(humans["target"]))
stats = F.target_level_model_stats(mods)
full, _ = F.build_frame(humans, mods, stats, chosen)
tl = V.target_level(full)
assert len(tl) == 578

# reproduction check (v1 H2)
repro = {}
for g in ("S", "P"):
    r = M.encompassing(tl, f"p_h_{g}", CFG.CLIP)
    got = (r["params"]["human_minus_model"], r["ci"].loc["human_minus_model", 0],
           r["ci"].loc["human_minus_model", 1])
    repro[g] = (got, all(round(x, 2) == y for x, y in zip(got, LOCKED[g])))
if not all(ok for _, ok in repro.values()):
    sys.exit(f"v1 H2 reproduction failed: {repro}; stopping before any v3 number.")

# Mens: v2 Amendment 2 reference column for M1
test_targets = set(tl["target"])
variants = list(V.build_variant_table(humans, mods, meta, rank, test_targets).index)
assert len(variants) == 34 and chosen in variants
sub = mods[mods["target"].isin(test_targets) & ~mods["imputed"]]
Pm = np.column_stack([tl["target"].map(sub[sub.model == m].set_index("target")["p"])
                      .to_numpy(float) for m in variants])
others = np.delete(Pm, variants.index(chosen), axis=1)
mens = np.nanmedian(others, axis=1)
mens_n = np.isfinite(others).sum(axis=1)
mens[mens_n < MIN_REF] = np.nan
assert np.isfinite(mens).all()

# Mnews, via the v1 loader with the scaffold filter widened to its scaffold
_saved = CFG.MATCHED_SCAFFOLDS
try:
    CFG.MATCHED_SCAFFOLDS = ("superforecaster with news 1",)
    nd, _ = F.load_matched_models()
finally:
    CFG.MATCHED_SCAFFOLDS = _saved
nd = nd[(nd.model == MNEWS) & ~nd["imputed"]].set_index("target")["p"]
mnews = tl["target"].map(nd).to_numpy(float)
assert np.isfinite(mnews).all()

y = tl["o"].to_numpy(float)
src = {"M1": tl["p_a"].to_numpy(float), "Mens": mens, "Mnews": mnews,
       "Hs": tl["p_h_S"].to_numpy(float), "Hp": tl["p_h_P"].to_numpy(float)}
for k, v in src.items():
    assert np.isfinite(v).all() and (v >= 0).all() and (v <= 1).all(), k

questions = sorted(humans["question"].unique())
qmap = {q: i for i, q in enumerate(questions)}
qcodes = tl["question"].map(qmap).to_numpy(np.int32)
n_q = len(questions)

# public forecasts per target, for the noise control
pub = full[full.GRP == "P"].groupby("target")["p_h"].apply(np.asarray)
pub_list = [pub[t] for t in tl["target"]]
n_pub = np.array([len(a) for a in pub_list])
n_sup = full[full.GRP == "S"].groupby("target").size().reindex(tl["target"]).to_numpy()


# ================================================================ folds
def fold_assign(codes, seed=FOLD_SEED, k=N_FOLDS):
    """Identical to the fold construction inside v2full.crossfit_gain."""
    rng = np.random.default_rng(seed)
    quniq = np.unique(codes)
    fold_of_q = {q: i % k for i, q in enumerate(rng.permutation(quniq))}
    return np.array([fold_of_q[q] for q in codes])


folds = fold_assign(qcodes)

# check: the v2 cross-fitted gain for M1 recomputed with these folds equals both
# v2full.crossfit_gain and the stored v2 point estimate
Est = pickle.loads((CFG.DERIVED / "v2_full_E_boot_crossfit.pkl").read_bytes())
vi = variants.index(chosen)
fold_check = {}
for g, h in (("S", "Hs"), ("P", "Hp")):
    la, lh = V.logit_clip(src["M1"]), V.logit_clip(src[h])
    ref, _ = W.crossfit_gain(y, la, lh, qcodes, seed=FOLD_SEED)
    d = np.empty(len(y))
    XA = np.column_stack([np.ones(len(y)), la]); XB = np.column_stack([XA, lh - la])
    for f in range(N_FOLDS):
        tr, te = folds != f, folds == f
        ba, _ = V.fast_logit(XA[tr], y[tr], qcodes[tr]); bb, _ = V.fast_logit(XB[tr], y[tr], qcodes[tr])
        pa = np.clip(1 / (1 + np.exp(-(XA[te] @ ba))), LO, HI)
        pb = np.clip(1 / (1 + np.exp(-(XB[te] @ bb))), LO, HI)
        d[te] = np.log(np.where(y[te] == 1, pb, 1 - pb)) - np.log(np.where(y[te] == 1, pa, 1 - pa))
    stored = float(Est["point"][g][vi])
    fold_check[g] = (float(d.mean()), ref, stored)
    assert abs(d.mean() - ref) < 1e-12 and abs(ref - stored) < 1e-12, fold_check[g]


# ================================================================ scoring
def logscore(p, yy):
    q = np.clip(p, LO, HI)
    return np.log(np.where(yy == 1, q, 1 - q))


def brier(p, yy):
    return (np.clip(p, 0, 1) - yy) ** 2


def sig(x):
    return 1 / (1 + np.exp(-x))


# ================================================================ combiners
def c1(ps):
    return np.mean(ps, axis=0)


def c2(ps):
    return sig(np.mean([V.logit_clip(p) for p in ps], axis=0))


def fit_c3(p, q, yy):
    d = p - q
    den = float(d @ d)
    wt = 0.5 if den <= 0 else float(d @ (yy - q)) / den
    return min(max(wt, 0.0), 1.0)


def fit_c3u(p, q, yy):
    X = np.column_stack([p, q])
    return np.linalg.lstsq(X, yy, rcond=None)[0]


def fit_c4(lp, lq, yy):
    r = minimize_scalar(lambda a: -logscore(sig(a * lp + (1 - a) * lq), yy).mean(),
                        bounds=(0.0, 1.0), method="bounded", options={"xatol": 1e-6})
    return float(r.x)


PAIRS = [("Hs", "M1"), ("Hp", "M1"), ("Hs", "Mens"), ("Hp", "Mens"), ("M1", "Mens"),
         ("N7", "M1"), ("N7", "Mens")]
TRIPLES = [("Hs", "M1", "Mens"), ("Hp", "M1", "Mens")]
ALONE = ["M1", "Mens", "Mnews", "Hs", "Hp"]
COMB = ["C1", "C2", "C3", "C3u", "C4"]
SYSTEMS = (ALONE + [f"{a}+{b}|{c}" for a, b in PAIRS for c in COMB]
           + [f"{'+'.join(t)}|{c}" for t in TRIPLES for c in ("C1", "C2")])


def oos(S, yy, fl, which=SYSTEMS):
    """Out-of-sample predictions for every system; returns (preds, weights).
    Weights for C3/C3u/C4 are fit on the training folds and frozen on the test fold."""
    pred, wts = {}, {}
    for s in which:
        name, _, c = s.partition("|")
        parts = name.split("+")
        if not c:
            pred[s] = S[name]; continue
        ps = [S[x] for x in parts]
        if c == "C1":
            pred[s] = c1(ps); continue
        if c == "C2":
            pred[s] = c2(ps); continue
        p, q = ps
        lp, lq = V.logit_clip(p), V.logit_clip(q)
        out = np.empty(len(yy)); ws = []
        for f in range(N_FOLDS):
            tr, te = fl != f, fl == f
            if c == "C3":
                a = fit_c3(p[tr], q[tr], yy[tr]); out[te] = a * p[te] + (1 - a) * q[te]
            elif c == "C3u":
                a = fit_c3u(p[tr], q[tr], yy[tr]); out[te] = a[0] * p[te] + a[1] * q[te]
            else:
                a = fit_c4(lp[tr], lq[tr], yy[tr]); out[te] = sig(a * lp[te] + (1 - a) * lq[te])
            ws.append(a)
        pred[s], wts[s] = out, np.array(ws)
    return pred, wts


def scores(pred, yy):
    return ({s: float(logscore(p, yy).mean()) for s, p in pred.items()},
            {s: float(brier(p, yy).mean()) for s, p in pred.items()})


# ================================================================ noise control
def noise_draw(rng):
    return np.array([np.median(rng.choice(a, size=NOISE_K, replace=False)) for a in pub_list])


assert (n_pub >= NOISE_K).all()
rng_noise = np.random.default_rng(SEED)
N7_draws = [noise_draw(rng_noise) for _ in range(NOISE_DRAWS)]
src["N7"] = N7_draws[0]                     # the one draw

noise_sys = [s for s in SYSTEMS if s.startswith("N7")]
noise_log, noise_bri = [], []
for nd_ in N7_draws:
    S2 = dict(src, N7=nd_)
    pr, _ = oos(S2, y, folds, noise_sys + ["M1", "Mens"]
                + [f"M1+Mens|{c}" for c in COMB])
    a, b = scores(pr, y)
    noise_log.append(a); noise_bri.append(b)
noise_log, noise_bri = pd.DataFrame(noise_log), pd.DataFrame(noise_bri)


# ================================================================ point
pred, wts = oos(src, y, folds)
LOG, BRI = scores(pred, y)

wrows = []
for s, a in wts.items():
    if a.ndim == 1:
        wrows.append(dict(system=s, weight="w(first)", mean=a.mean(), sd=a.std(ddof=1),
                          min=a.min(), max=a.max()))
    else:
        for j, nm in enumerate(("w(first)", "w(second)")):
            wrows.append(dict(system=s, weight=nm, mean=a[:, j].mean(), sd=a[:, j].std(ddof=1),
                              min=a[:, j].min(), max=a[:, j].max()))
WT = pd.DataFrame(wrows)
constrained = WT[WT.system.str.endswith("|C3") | WT.system.str.endswith("|C4")]
sd_flag = bool((constrained["sd"] > SD_RULE).any())


# ================================================================ bootstrap
idx_q = [np.flatnonzero(qcodes == q) for q in range(n_q)]
rng = np.random.default_rng(SEED)
BL = np.full((DRAWS, len(SYSTEMS)), np.nan); BB = np.full_like(BL, np.nan)
for t in range(DRAWS):
    pick = rng.integers(0, n_q, n_q)
    rows = np.concatenate([idx_q[q] for q in pick])
    clus = np.concatenate([np.full(len(idx_q[q]), j) for j, q in enumerate(pick)])
    fl = fold_assign(clus)                  # v2 bootstrap convention: refold on draw clusters
    Sb = {k: v[rows] for k, v in src.items()}
    pr, _ = oos(Sb, y[rows], fl)
    a, b = scores(pr, y[rows])
    BL[t] = [a[s] for s in SYSTEMS]; BB[t] = [b[s] for s in SYSTEMS]
    if (t + 1) % 500 == 0:
        print(f"boot {t+1}/{DRAWS}  {time.time()-T0:.0f}s", flush=True)
BL = pd.DataFrame(BL, columns=SYSTEMS); BB = pd.DataFrame(BB, columns=SYSTEMS)


def diff(a, b):
    """Improvement of system a over b: log score a-b, Brier b-a (positive favors a)."""
    dl = LOG[a] - LOG[b]; db = BRI[b] - BRI[a]
    l_lo, l_hi = V.pct_ci(BL[a] - BL[b]); b_lo, b_hi = V.pct_ci(BB[b] - BB[a])
    return dict(a=a, b=b, d_log=dl, log_lo=l_lo, log_hi=l_hi,
                d_brier=db, brier_lo=b_lo, brier_hi=b_hi)


def win(r, sc):
    return r[f"{sc}_lo"] > 0


# ================================================================ claims
CARRY = ["C1", "C2"] if sd_flag else ["C1", "C2", "C3", "C4"]
HN = {"S": "Hs", "P": "Hp"}
GL = {"S": "superforecaster median", "P": "public median"}
claims, coprim = {}, {}
for g, h in HN.items():
    for c in COMB:
        r1 = diff(f"{h}+M1|{c}", "M1")
        r2 = diff(f"{h}+M1|{c}", f"M1+Mens|{c}")
        r3 = diff(f"{h}+Mens|{c}", "Mens")
        claims[(g, c)] = dict(vsM1=r1, vsM1Mens=r2,
                              log=win(r1, "log") and win(r2, "log"),
                              brier=win(r1, "brier") and win(r2, "brier"))
        coprim[(g, c)] = dict(r=r3, log=win(r3, "log"), brier=win(r3, "brier"))

# noise vs superforecaster against Mens (log score)
noise_cmp = {}
for c in COMB:
    nd_l = noise_log[f"N7+Mens|{c}"] - noise_log["Mens"]
    band = (float(np.percentile(nd_l, 2.5)), float(np.percentile(nd_l, 97.5)))
    s_d = LOG[f"Hs+Mens|{c}"] - LOG["Mens"]
    p_d = LOG[f"Hp+Mens|{c}"] - LOG["Mens"]
    noise_cmp[c] = dict(n7_one=LOG[f"N7+Mens|{c}"] - LOG["Mens"],
                        n7_med=float(np.median(nd_l)), band=band, s=s_d, p=p_d,
                        s_in_band=band[0] <= s_d <= band[1])


# ================================================================ report helpers
def f3(x):
    return f"{x:+.3f}"


def ci3(lo, hi):
    return f"[{lo:+.3f}, {hi:+.3f}]"


def lab(s):
    return (s.replace("Hs", "H_S").replace("Hp", "H_P").replace("|", " · "))


def claim_sentence(g):
    held = [c for c in CARRY if claims[(g, c)]["log"]]
    if held:
        return (f"{GL[g]}: deployable increment claimed under {', '.join(held)} "
                f"(human + M1 beats M1 alone and M1 + Mens on log score, both intervals above zero)")
    return (f"{GL[g]}: no deployable increment claimed — under none of {', '.join(CARRY)} does "
            f"human + M1 beat both M1 alone and M1 + Mens on log score with both intervals above zero")


def coprim_sentence(g):
    held = [c for c in CARRY if coprim[(g, c)]["log"]]
    if held:
        return f"{GL[g]}: human + Mens beats Mens alone on log score under {', '.join(held)}"
    return f"{GL[g]}: human + Mens does not beat Mens alone on log score under any of {', '.join(CARRY)}"


git_head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=CFG.REPO_ROOT).stdout.strip()

LOCKED_READING = [
    "\"The human median carries a deployable increment\" is claimed only if human + M1 beats M1 "
    "alone AND beats M1 + Mens on the primary score, with both bootstrap intervals excluding zero. "
    "Beating M1 alone is not enough; any second forecast improves a single model.",
    "human + Mens versus Mens alone is the co-primary question: whether the human median adds to "
    "the ensemble. This is the decision version of the v2 reference curve.",
    "If the log score and Brier disagree on a claim, the paper takes no side and states the "
    "disagreement in one sentence with a pointer to the companion methods paper.",
    "The public and superforecaster results are read separately. A claim that holds for "
    "superforecasters and not for the public is stated as a claim about the superforecaster median "
    "under tournament and web-search conditions, not about \"humans\".",
    "If a fitted weight's fold-to-fold SD exceeds 0.2, the optimized combiners (C3, C4) are "
    "reported as descriptive only and the equal-weight rows carry the claim.",
    "If the 7-person public median behaves like the superforecaster median against Mens, the "
    "superforecaster exception in v2 is read as a sample-size effect, not a group effect.",
    "No switching rules by disagreement (DIS) are fitted. That question was H3 and is closed.",
]


# ================================================================ report
w("# SPEC v3 Amendment 6: out-of-sample combination")
w()
w("Post-results in origin; reading locked in specs/forecast_spec_v3.md "
  f"(commit `{SPEC_COMMIT[:7]}`) before computation. No v1 or v2 number changes.")
w()
w("## Locked reading (restated from SPEC v3)")
w()
for s in LOCKED_READING:
    w(f"- {s}")
w()
w("## Result against the locked reading")
w()
w(f"- Weight-stability rule: {'at least one constrained C3/C4 weight has fold-to-fold SD > 0.2, so C3 and C4 are descriptive only and C1/C2 carry the claims' if sd_flag else 'no constrained C3/C4 weight has fold-to-fold SD > 0.2, so C1–C4 can all carry claims'} "
  f"(max constrained SD = {constrained['sd'].max():.3f}).")
for g in ("S", "P"):
    w(f"- Deployable increment, {claim_sentence(g)}.")
for g in ("S", "P"):
    w(f"- Co-primary, {coprim_sentence(g)}.")
dis = [(g, c, k) for g in ("S", "P") for c in CARRY
       for k, d in (("deployable", claims[(g, c)]), ("co-primary", coprim[(g, c)]))
       if d["log"] != d["brier"]]
if dis:
    w("- Log score and Brier disagree on: "
      + "; ".join(f"{GL[g]} {k} under {c} (log {'yes' if (claims if k=='deployable' else coprim)[(g,c)]['log'] else 'no'}, "
                  f"Brier {'yes' if (claims if k=='deployable' else coprim)[(g,c)]['brier'] else 'no'})"
                  for g, c, k in dis)
      + ". Per the locked reading the paper takes no side on these and points to the companion methods paper.")
else:
    w("- Log score and Brier agree on every claim above.")
nb = [c for c in CARRY if noise_cmp[c]["s_in_band"]]
w(f"- Noise control: the superforecaster median's log-score improvement over Mens (human + Mens vs "
  f"Mens) lies inside the {NOISE_DRAWS}-draw 95% band of the 7-person public median's improvement under "
  f"{', '.join(nb) if nb else 'none'} of {', '.join(CARRY)}. "
  + ("By the operationalization below, the 7-person median behaves like the superforecaster median "
     "against Mens, and the v2 superforecaster exception is read as a sample-size effect."
     if len(nb) == len(CARRY) else
     "By the operationalization below, the 7-person median does not behave like the superforecaster "
     "median against Mens, so the v2 superforecaster exception is not read as a sample-size effect."
     if not nb else
     "The combiners split, so no reading of the v2 exception is drawn."))
s_only = [g for g in ("S",) if any(claims[("S", c)]["log"] for c in CARRY)
          and not any(claims[("P", c)]["log"] for c in CARRY)]
if s_only:
    w("- The deployable-increment claim holds for superforecasters and not for the public, so it is "
      "stated as a claim about the superforecaster median under tournament and web-search "
      "conditions, not about \"humans\".")
w()
w("Descriptive notes (added after review; no new claims, no number changed):")
w()


def dstr(r):
    return (f"log {f3(r['d_log'])} {ci3(r['log_lo'], r['log_hi'])}, "
            f"Brier {f3(r['d_brier'])} {ci3(r['brier_lo'], r['brier_hi'])}")


hs_m1 = diff("Hs", "M1")
hs_c = {c: diff("Hs", f"Hs+M1|{c}") for c in ("C1", "C2")}
w(f"- For the superforecaster median, C3 and C4 put weight 1.000 on the human in every fold "
  f"(H_S+M1 and H_S+Mens), so the best fitted pool is the superforecaster median alone. "
  f"H_S alone vs M1: {dstr(hs_m1)}. H_S alone vs H_S+M1 · C1: {dstr(hs_c['C1'])}. "
  f"H_S alone vs H_S+M1 · C2: {dstr(hs_c['C2'])}.")


def c3u_str(s):
    a = wts[s]
    return (f"w(human) {a[:, 0].mean():.3f} (fold SD {a[:, 0].std(ddof=1):.3f}), "
            f"w(M1) {a[:, 1].mean():.3f} (fold SD {a[:, 1].std(ddof=1):.3f})")


w(f"- Fitted C3u weights (secondary), mean over the 5 folds: H_S+M1 {c3u_str('Hs+M1|C3u')}; "
  f"H_P+M1 {c3u_str('Hp+M1|C3u')}.")
mm = diff("Mens", "M1")
w(f"- Mens alone scores worse than M1 (log score {LOG['Mens']:.3f} vs {LOG['M1']:.3f}; Brier "
  f"{BRI['Mens']:.3f} vs {BRI['M1']:.3f}), so M1+Mens under equal weights is worse than M1 "
  f"(C1 log {LOG['M1+Mens|C1']:.3f}, C2 log {LOG['M1+Mens|C2']:.3f}) and \"beats M1+Mens\" is the "
  f"weaker of the two conditions; the binding condition is \"beats M1\".")
mn = diff("Mnews", "M1")
w(f"- Mnews alone: log score {LOG['Mnews']:.3f}, Brier {BRI['Mnews']:.3f}; Mnews vs M1: {dstr(mn)}.")
w()
w("## Setup")
w()
w(f"- 578 targets on {n_q} questions; one row per target. Sources: M1 = benchmark (a) `{chosen}`; "
  f"Mnews = `{MNEWS}`; Mens = median of the 33 matched variants other than M1 (v2 Amendment 2 "
  f"reference; contributors per target {mens_n.min()}–{mens_n.max()}); H_S, H_P = group medians.")
w(f"- Folds: v2 cross-fit folds (5, by question, seed {FOLD_SEED}). Check: the v2 cross-fitted "
  f"log-score gain for M1 recomputed on these folds equals the stored v2 point estimate "
  + "; ".join(f"{g} {v[0]:.6f} vs {v[2]:.6f}" for g, v in fold_check.items()) + ".")
w(f"- Scores: log score = mean log probability on the outcome, probabilities clipped to {CFG.CLIP} "
  "(v1/v2 convention; primary); Brier = mean squared error on the unclipped probability (clipped "
  "to [0, 1] only for C3u). Differences are written as the improvement of the first system over "
  "the second: log a − log b, Brier b − a; positive favors the first.")
w("- Combiners: C1 mean of probabilities; C2 mean of logits (inputs clipped as above); C3 linear "
  "weight w ∈ [0, 1] on the first source, 1 − w on the second, minimizing training-fold Brier "
  "(closed form, then clipped); C3u unconstrained linear weights, no intercept, least squares "
  "(secondary; this reading of the spec's \"unconstrained weights\" is not fixed by the spec, chosen "
  "here post-spec and flagged); C4 log-pool weight w ∈ [0, 1] minimizing training-fold log score. Weights frozen "
  "on the test fold.")
w(f"- Noise control N7: median of {NOISE_K} public forecasts drawn without replacement on each "
  f"target (public forecasters per target {n_pub.min()}–{n_pub.max()}; superforecasters per target "
  f"median {int(np.median(n_sup))}, range {n_sup.min()}–{n_sup.max()}). Seed {SEED}; draw 1 is the "
  f"reported draw and enters the bootstrap; {NOISE_DRAWS} draws give the median and 2.5–97.5% band.")
w(f"- Intervals: question-level cluster bootstrap, {DRAWS} draws, seed {SEED}; within each draw "
  "duplicated questions are distinct clusters, folds are reassigned on the draw's clusters with "
  "the v2 fold rule (as in the v2 cross-fit bootstrap), and C3/C3u/C4 weights are refit. "
  "Percentile intervals.")
w()
w("## Systems: pooled out-of-sample scores")
w()
rows = []
for s in SYSTEMS:
    rows.append(dict(system=lab(s), log_score=f"{LOG[s]:.3f}", brier=f"{BRI[s]:.3f}"))
w(md_table(pd.DataFrame(rows).set_index("system")))
w()
w("## Deployable increment: human + M1 vs M1 alone, and vs M1 + Mens")
w()


def dtab(rs):
    t = pd.DataFrame([dict(comparison=f"{lab(r['a'])}  vs  {lab(r['b'])}",
                           d_log=f3(r["d_log"]), log_ci=ci3(r["log_lo"], r["log_hi"]),
                           d_brier=f3(r["d_brier"]), brier_ci=ci3(r["brier_lo"], r["brier_hi"]))
                      for r in rs])
    return md_table(t.set_index("comparison"))


for g in ("S", "P"):
    w(f"**{GL[g].capitalize()}**")
    w()
    rs = []
    for c in COMB:
        rs += [claims[(g, c)]["vsM1"], claims[(g, c)]["vsM1Mens"]]
    w(dtab(rs))
    w()
w("## Co-primary: human + Mens vs Mens alone")
w()
w(dtab([coprim[(g, c)]["r"] for g in ("S", "P") for c in COMB]))
w()
w("## Other comparisons")
w()
other = [diff(x, "M1") for x in ("Mens", "Mnews", "Hs", "Hp")]
other += [diff(x, "Mens") for x in ("Hs", "Hp")]
other += [diff(f"{h}+M1+Mens|{c}", f"M1+Mens|{c}") for h in ("Hs", "Hp") for c in ("C1", "C2")]
other += [diff(f"{h}+M1+Mens|{c}", f"{h}+Mens|{c}") for h in ("Hs", "Hp") for c in ("C1", "C2")]
w(dtab(other))
w()
w("## Noise control (N7, 7-person public median)")
w()
w("Draw 1 with bootstrap intervals:")
w()
nrs = []
for c in COMB:
    nrs += [diff(f"N7+M1|{c}", "M1"), diff(f"N7+M1|{c}", f"M1+Mens|{c}"), diff(f"N7+Mens|{c}", "Mens")]
w(dtab(nrs))
w()
w(f"Across {NOISE_DRAWS} draws, log-score improvement (median [2.5%, 97.5%]), next to the two "
  "group medians:")
w()
nt = []
for c in COMB:
    for lab_, a, b in (("N7 + M1 vs M1", f"N7+M1|{c}", "M1"),
                       ("N7 + M1 vs M1 + Mens", f"N7+M1|{c}", f"M1+Mens|{c}"),
                       ("N7 + Mens vs Mens", f"N7+Mens|{c}", "Mens")):
        dd = noise_log[a] - noise_log[b]
        nt.append(dict(combiner=c, comparison=lab_,
                       n7=f"{np.median(dd):+.3f} [{np.percentile(dd, 2.5):+.3f}, {np.percentile(dd, 97.5):+.3f}]",
                       H_S=f3(LOG[a.replace("N7", "Hs")] - LOG[b]),
                       H_P=f3(LOG[a.replace("N7", "Hp")] - LOG[b])))
w(md_table(pd.DataFrame(nt).set_index(["combiner", "comparison"])))
w()
w("Operationalization of \"behaves like the superforecaster median against Mens\" (not fixed by "
  "the spec; chosen here post-spec and flagged): the superforecaster median's point log-score improvement of "
  "human + Mens over Mens lies inside the 200-draw 2.5–97.5% band of the same quantity for N7, "
  "for each claim-carrying combiner.")
w()
w("## Fitted weights: fold-to-fold variation (point fit)")
w()
WTs = WT.copy()
WTs["system"] = WTs["system"].map(lab)
for c in ("mean", "sd", "min", "max"):
    WTs[c] = WTs[c].map(lambda x: f"{x:.3f}")
w(md_table(WTs.set_index(["system", "weight"])))
w()
w("`w(first)` is the weight on the first-named source (the human, N7 or M1). The SD rule is applied "
  "to the constrained C3 and C4 weights; C3u is secondary and reported only.")
w()
w("## Checklist")
w()
w(f"- Spec commit: `{SPEC_COMMIT}`. Repo HEAD at run: `{git_head}`. Amendment 6 results not committed.")
w("- Locked reading: restated above.")
for g in ("S", "P"):
    w(f"- Branch, deployable increment, {claim_sentence(g)}.")
    w(f"- Branch, co-primary, {coprim_sentence(g)}.")
w(f"- Reproduction check (untouched v1 H2 path, pooled, clip (0.01, 0.99)): "
  + "; ".join(f"{g} {got[0]:.2f} [{got[1]:.2f}, {got[2]:.2f}] vs locked "
              f"{LOCKED[g][0]:.2f} [{LOCKED[g][1]:.2f}, {LOCKED[g][2]:.2f}] — "
              f"{'match' if ok else 'MISMATCH'}" for g, (got, ok) in repro.items()) + ".")
w(f"- Runtime {time.time()-T0:.0f}s.")
w()

(CFG.DOCS / "amendment6_REPORT.md").write_text("\n".join(OUT))
print("\n".join(OUT))
