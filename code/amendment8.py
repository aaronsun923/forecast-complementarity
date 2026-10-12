"""SPEC v3 Amendment 8: leaderboard levels and equivalent model upgrade.

Locked in specs/forecast_spec_v3.md at 80236ad (amendment and pre-run clarifications), before this
file was written or run. Nothing here changes a v1, v2, P5 or Amendment 6/7 number.

Reads the existing derived frame (data/derived/full_frame.pkl, the v1 H1 frame) and the 34
matched-variant forecasts through the v1/v2 loaders, as Amendment 7 does. No new download, no
new model run. The bootstrap draws are Amendment 7's (seed 20260906, one integers() call of
shape (2000, 162)); the folds are Amendment 6's (v2 cross-fit rule, seed 20260908), assigned on
all 578 targets and then restricted to T, and reassigned on each draw's clusters.

Score orientation: every "score(x) - score(y)" in the spec is taken as a loss difference (Brier,
and log loss = -log score), so every gain below is positive when the second-named system wins.
Log scores in the leaderboard are reported as mean log score (higher = better).

Usage:  python3 code/amendment8.py
Writes: docs/amendment8_REPORT.md, docs/amendment8_leaderboard.csv, docs/amendment8_averaging.csv,
        docs/amendment8_upgrade.csv, docs/figures/a8_leaderboard.png, docs/figures/a8_upgrade.png
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
from scipy.stats import spearmanr

import config as CFG
import fbdata as F
import v2common as V
from report import md_table

T0 = time.time()
warnings.filterwarnings("ignore")
SPEC_COMMIT = "80236ad105365ba1d8cb896830ff6dc0bf84122b"
M1 = "Claude-3-5-Sonnet-20240620 (zero shot with freeze values)"
SEED = 20260906               # Amendments 6, 7: bootstrap seed
FOLD_SEED = 20260908          # Amendment 6: v2 cross-fit folds
N_FOLDS = 5
DRAWS = 2000
SD_RULE = 0.2                 # Amendment 6 weight-stability rule
MIN_ROWS = 10                 # item 2: forecasters with at least 10 non-imputed rows for m
LO, HI = CFG.CLIP
RULES = ("log", "brier")      # clarification 3: log score primary, Brier beside it
RULE_NAME = {"log": "log score", "brier": "Brier ×100"}
GROUPS = ("S", "P")
GNAME = {"S": "superforecaster", "P": "public"}
INDNAME = {"S": "mean individual superforecaster", "P": "mean individual public forecaster"}
HEAD = {"S": "Superforecasters", "P": "Public forecasters"}
HMED = {"S": "p_h_S", "P": "p_h_P"}

OUT = []
def w(s=""):
    OUT.append(s)


def stop(msg):
    print("STOP:", msg, flush=True)
    sys.exit(msg)


def loss(p, y, rule):
    """Loss orientation: Brier ×100, or log loss with probabilities clipped to [0.01, 0.99]."""
    if rule == "brier":
        return 100 * (p - y) ** 2
    q = np.clip(p, LO, HI)
    return -np.log(np.where(y == 1, q, 1 - q))


def fold_assign(codes, seed=FOLD_SEED, k=N_FOLDS):
    """Amendment 6 fold rule (identical to the fold construction inside v2full.crossfit_gain)."""
    rng = np.random.default_rng(seed)
    quniq = np.unique(codes)
    fold_of_q = {q: i % k for i, q in enumerate(rng.permutation(quniq))}
    return np.array([fold_of_q[q] for q in codes])


# ==================================================================== load
full = pd.read_pickle(CFG.DERIVED / "full_frame.pkl")
if len(full) != 33334 or full["target"].nunique() != 578 or full["question"].nunique() != 162:
    stop(f"derived frame is not the v1 H1 frame: {len(full)} rows, {full['target'].nunique()} targets")
mods, meta = F.load_matched_models()
hum_targets = set(full["target"])
rank_sel, chosen, _ = F.select_baseline_a(mods, hum_targets)
assert chosen == M1
tab = V.build_variant_table(full, mods, meta, rank_sel, hum_targets)   # Q_m, sorted by Q
variants = list(tab.index)
assert len(variants) == 34
Qv = tab["Q_m"].to_numpy(float)
QRANK = {m: i + 1 for i, m in enumerate(variants)}                       # selection-set Q order
test = mods[mods["target"].isin(hum_targets)]
questions = sorted(full["question"].unique())
qmap = {q: i for i, q in enumerate(questions)}
n_q = len(questions)
rng = np.random.default_rng(SEED)
PICKS = rng.integers(0, n_q, (DRAWS, n_q))       # Amendment 7's draws: one set for every quantity


def boot_mean(values, qcodes):
    """Mean over rows and its question-cluster bootstrap percentile interval (shared PICKS)."""
    s = np.bincount(qcodes, weights=values, minlength=n_q)
    n = np.bincount(qcodes, minlength=n_q)
    b = s[PICKS].sum(1) / n[PICKS].sum(1)
    lo, hi = np.percentile(b, [2.5, 97.5])
    return float(s.sum() / n.sum()), float(lo), float(hi)


def boot_means(L, qcodes):
    """Column means of L (rows x k) and their per-draw values under the shared PICKS."""
    S = np.stack([np.bincount(qcodes, weights=L[:, j], minlength=n_q) for j in range(L.shape[1])], 1)
    n = np.bincount(qcodes, minlength=n_q).astype(float)
    B = np.stack([S[p].sum(0) / n[p].sum() for p in PICKS])
    return S.sum(0) / n.sum(), B


def better_count(v, ref):
    """Rank among the 34 variants plus the entry itself: 1 + number of variants strictly better
    (lower loss). v: (..., 34) variant losses; ref: (...) entry loss."""
    return 1 + (v < ref[..., None]).sum(-1)


# ==================================================================== target level and T
tl = V.target_level(full)
assert len(tl) == 578
y = tl["o"].to_numpy(float)
qc = tl["question"].map(qmap).to_numpy(np.int32)
nonimp = test[~test["imputed"].astype(bool)]
P = np.column_stack([tl["target"].map(nonimp[nonimp["model"] == m].set_index("target")["p"])
                     .to_numpy(float) for m in variants])
H = {g: tl[HMED[g]].to_numpy(float) for g in GROUPS}
T = np.isfinite(P).all(1) & np.isfinite(H["S"]) & np.isfinite(H["P"])
nT, qT = int(T.sum()), int(np.unique(qc[T]).size)
n_all34 = int(np.isfinite(P).all(1).sum())
print(f"|T| = {nT} targets on {qT} questions", flush=True)
if nT < 300:
    stop(f"|T| = {nT} < 300: the spec's larger-set leaderboard is required and is not implemented here")
iT = np.flatnonzero(T)
yT, qcT, PT = y[iT], qc[iT], P[iT]
HT = {g: H[g][iT] for g in GROUPS}


# ============================================ reproduction check (Amendment 7 G_B(M1), item 2 rows)
def variant_rows(m):
    """Clarification 1: every row of the v1 H1 frame where m's forecast is non-imputed."""
    fm = test[test["model"] == m].set_index("target")
    p = full["target"].map(fm["p"])
    imp = full["target"].map(fm["imputed"]).fillna(True).astype(bool)
    keep = p.notna() & ~imp
    d = full.loc[keep, ["GRP", "question", "target", "forecaster", "p_h", "o"]].copy()
    d["p_m"] = p[keep].to_numpy(float)
    return d, int((~keep).sum())


A7 = pd.read_csv(CFG.DOCS / "amendment7_pervariant.csv").set_index("variant")
d1, drop1 = variant_rows(M1)
qc1 = d1["question"].map(qmap).to_numpy()
gb1 = 100 * ((d1["p_m"] - d1["o"]) ** 2 - (d1["p_h"] - d1["o"]) ** 2).to_numpy()
REPRO = {}
for g in GROUPS:
    k = (d1["GRP"] == g).to_numpy()
    got = boot_mean(gb1[k], qc1[k])
    ref = tuple(float(A7.loc[M1, c]) for c in (f"G_B_{g}", f"G_B_{g}_lo", f"G_B_{g}_hi"))
    n_ref = int(A7.loc[M1, f"n_rows_{g}"])
    ok = int(k.sum()) == n_ref and all(abs(a - b) < 5e-7 for a, b in zip(got, ref))
    REPRO[g] = dict(got=got, ref=ref, n=int(k.sum()), n_ref=n_ref, ok=ok)
print("reproduction:", {g: (round(r["got"][0], 4), r["ok"]) for g, r in REPRO.items()}, flush=True)
if drop1 != 0 or not all(r["ok"] for r in REPRO.values()):
    stop(f"Amendment 7 G_B(M1) does not reproduce on the Amendment 8 rows: {REPRO}")


# ============================================ item 1: leaderboard of levels on T
# Variant and human-median losses per target on T; per-draw means under the shared PICKS.
LB, VB = {}, {}            # point means and draws, keyed by rule; columns: 34 variants, Hp, Hs
for rule in RULES:
    L = np.column_stack([loss(PT, yT[:, None], rule)] + [loss(HT[g], yT, rule)[:, None] for g in ("P", "S")])
    LB[rule], VB[rule] = boot_means(L, qcT)
# mean individual forecaster on T (reference line only)
rowsT = full[full["target"].isin(set(tl["target"].to_numpy()[iT]))]
IND = {}
for g in GROUPS:
    r = rowsT[rowsT["GRP"] == g]
    IND[g] = {rule: float(loss(r["p_h"].to_numpy(float), r["o"].to_numpy(float), rule).mean()) for rule in RULES}
    IND[g]["n_rows"] = len(r)

VRANK, LEAD = {}, []
for rule in RULES:
    vm = LB[rule][:34]
    VRANK[rule] = np.array([1 + (np.delete(vm, j) < vm[j]).sum() for j in range(34)])
    sgn = -1 if rule == "log" else 1                    # report log as mean log score
    for j, m in enumerate(variants):
        LEAD.append(dict(entry=m, kind="variant", rule=rule, score=sgn * vm[j], rank=int(VRANK[rule][j]),
                         rank_lo=np.nan, rank_hi=np.nan, Q=Qv[j], Q_rank=j + 1))
    for c, g in ((34, "P"), (35, "S")):
        rk = int(better_count(vm, np.array(LB[rule][c])))
        draws = better_count(VB[rule][:, :34], VB[rule][:, c])
        lo, hi = np.percentile(draws, [2.5, 97.5])
        LEAD.append(dict(entry=f"{GNAME[g]} median", kind="human median", rule=rule, score=sgn * LB[rule][c],
                         rank=rk, rank_lo=lo, rank_hi=hi, Q=np.nan, Q_rank=np.nan))
    for g in GROUPS:
        LEAD.append(dict(entry=INDNAME[g], kind="reference line", rule=rule,
                         score=sgn * IND[g][rule], rank=int(better_count(vm, np.array(IND[g][rule]))),
                         rank_lo=np.nan, rank_hi=np.nan, Q=np.nan, Q_rank=np.nan))
LEAD = pd.DataFrame(LEAD)
BEST = {rule: int(np.argmin(LB[rule][:34])) for rule in RULES}           # clarification 2: score on T
SPEAR = {rule: spearmanr(Qv, LB[rule][:34]) for rule in RULES}
print(f"item 1 done {time.time() - T0:.0f}s", flush=True)


# ============================================ item 2: averaging rule for an individual
AV = []
helped_detail = {}
for m in variants:
    d, dropped = variant_rows(m)
    qcd = d["question"].map(qmap).to_numpy()
    o, h, pm = d["o"].to_numpy(float), d["p_h"].to_numpy(float), d["p_m"].to_numpy(float)
    a = (h + pm) / 2                                                      # C1 pool, no fitting
    for g in GROUPS:
        k = (d["GRP"] == g).to_numpy()
        r = dict(variant=m, Q=float(tab.loc[m, "Q_m"]), Q_rank=QRANK[m], group=g,
                 rows_dropped_imputed=dropped, n_rows=int(k.sum()))
        for rule in RULES:
            g_ai = loss(pm, o, rule) - loss(a, o, rule)                  # averaging vs AI alone
            g_own = loss(h, o, rule) - loss(a, o, rule)                  # averaging vs own forecast
            r[f"gain_vs_ai_{rule}"], r[f"gain_vs_ai_{rule}_lo"], r[f"gain_vs_ai_{rule}_hi"] = boot_mean(g_ai[k], qcd[k])
            r[f"gain_vs_own_{rule}"], r[f"gain_vs_own_{rule}_lo"], r[f"gain_vs_own_{rule}_hi"] = boot_mean(g_own[k], qcd[k])
            per = pd.Series(g_ai[k]).groupby(d.loc[k, "forecaster"].to_numpy()).agg(["mean", "size"])
            per = per[per["size"] >= MIN_ROWS]
            r[f"share_helped_{rule}"] = float((per["mean"] > 0).mean()) if len(per) else np.nan
            r[f"n_forecasters_{rule}"] = int(len(per))
        AV.append(r)
AV = pd.DataFrame(AV)

THR = {}
for g in GROUPS:
    for rule in RULES:
        sub = AV[AV["group"] == g].sort_values("Q_rank")
        pos = sub[sub[f"gain_vs_ai_{rule}_lo"] > 0]
        if pos.empty:
            THR[(g, rule)] = dict(X=None, n_pos=0, exceptions=[])
        else:
            X = int(pos["Q_rank"].min())
            below = sub[sub["Q_rank"] >= X]
            exc = below[below[f"gain_vs_ai_{rule}_lo"] <= 0]["variant"].tolist()
            THR[(g, rule)] = dict(X=X, variant=pos.iloc[0]["variant"], n_pos=len(pos), exceptions=exc)
print(f"item 2 done {time.time() - T0:.0f}s", flush=True)


# ============================================ item 3: equivalent model upgrade on T
folds_all = fold_assign(qc)                    # Amendment 6 fold assignment on all 578 targets


def c3_oos(Pm, h, yy, fl):
    """C3 for every variant at once: w on the human median in [0, 1], 1 - w on m, fit on the
    training folds by closed-form Brier minimization then clipped (Amendment 6 fit_c3), frozen
    on the test fold. Returns out-of-fold predictions (n x 34) and weights (folds x 34)."""
    D = h[:, None] - Pm
    out = np.empty_like(Pm)
    W_ = np.full((N_FOLDS, Pm.shape[1]), np.nan)
    for f in range(N_FOLDS):
        tr, te = fl != f, fl == f
        if not te.any():
            continue
        if tr.any():
            den = (D[tr] ** 2).sum(0)
            num = (D[tr] * (yy[tr, None] - Pm[tr])).sum(0)
            wt = np.where(den > 0, num / np.where(den > 0, den, 1), 0.5)
        else:
            wt = np.full(Pm.shape[1], 0.5)
        wt = np.clip(wt, 0, 1)
        W_[f] = wt
        out[te] = Pm[te] + wt * D[te]
    return out, W_


def item3_stats(Pm, Hd, yy, fl):
    """Mean losses on the given T rows: variants alone, and m + g under C1 and C3."""
    res = {}
    for rule in RULES:
        res[("alone", rule)] = loss(Pm, yy[:, None], rule).mean(0)
    wts = {}
    for g in GROUPS:
        c1 = (Pm + Hd[g][:, None]) / 2
        c3, wts[g] = c3_oos(Pm, Hd[g], yy, fl)
        for rule in RULES:
            res[(g, "C1", rule)] = loss(c1, yy[:, None], rule).mean(0)
            res[(g, "C3", rule)] = loss(c3, yy[:, None], rule).mean(0)
    return res, wts


def item3_readouts(res):
    """U, F and the top variant's own gain, per (g, combiner, rule); best variant's identity fixed
    at the point estimate (BEST)."""
    out = {}
    for rule in RULES:
        va = res[("alone", rule)]
        rk_alone = np.array([1 + (np.delete(va, j) < va[j]).sum() for j in range(34)])
        b = BEST[rule]
        for g in GROUPS:
            for c in ("C1", "C3"):
                vc = res[(g, c, rule)]
                rk_comb = better_count(va[None, :].repeat(34, 0), vc)
                den = va - va[b]
                with np.errstate(divide="ignore", invalid="ignore"):
                    Fv = (va - vc) / den
                Fv[b] = np.nan
                out[(g, c, rule)] = dict(rank_m=rk_alone, rank_comb=rk_comb, U=rk_alone - rk_comb, F=Fv,
                                         top_gain=va[b] - vc[b], alone=va, comb=vc)
    return out


PT_fold = folds_all[iT]
RES, WTS = item3_stats(PT, HT, yT, PT_fold)
R3 = item3_readouts(RES)
WSD = {g: np.nanstd(WTS[g], axis=0, ddof=1) for g in GROUPS}
WMEAN = {g: np.nanmean(WTS[g], axis=0) for g in GROUPS}
sd_flag = bool(max(WSD[g].max() for g in GROUPS) > SD_RULE)

# bootstrap: Amendment 7 draws; folds reassigned on the draw's clusters over all 578 targets, then
# restricted to T (clarification 4); C3 refit in each draw
idx_q = [np.flatnonzero(qc == q) for q in range(n_q)]
BU = {k: np.full((DRAWS, 34), np.nan) for k in R3}
BF = {k: np.full((DRAWS, 34), np.nan) for k in R3}
BTOP = {k: np.full(DRAWS, np.nan) for k in R3}
for t in range(DRAWS):
    pick = PICKS[t]
    rws = np.concatenate([idx_q[q] for q in pick])
    clus = np.concatenate([np.full(len(idx_q[q]), i) for i, q in enumerate(pick)])
    fl = fold_assign(clus)
    k = T[rws]
    r_, f_ = rws[k], fl[k]
    res_b, _ = item3_stats(P[r_], {g: H[g][r_] for g in GROUPS}, y[r_], f_)
    rb = item3_readouts(res_b)
    for key, v in rb.items():
        BU[key][t], BF[key][t], BTOP[key][t] = v["U"], v["F"], v["top_gain"]
    if (t + 1) % 500 == 0:
        print(f"  item 3 bootstrap {t + 1}/{DRAWS} {time.time() - T0:.0f}s", flush=True)

UP = []
for (g, c, rule), v in R3.items():
    for j, m in enumerate(variants):
        u_lo, u_hi = V.pct_ci(BU[(g, c, rule)][:, j])
        f_lo, f_hi = V.pct_ci(BF[(g, c, rule)][:, j])
        is_best = j == BEST[rule]
        t_lo, t_hi = V.pct_ci(BTOP[(g, c, rule)]) if is_best else (np.nan, np.nan)
        sgn = -1 if rule == "log" else 1
        UP.append(dict(variant=m, Q=Qv[j], Q_rank=j + 1, group_median=g, combiner=c, rule=rule,
                       score_m=sgn * v["alone"][j], score_m_plus_g=sgn * v["comb"][j],
                       rank_m=int(v["rank_m"][j]), rank_m_plus_g=int(v["rank_comb"][j]),
                       U=int(v["U"][j]), U_lo=u_lo, U_hi=u_hi,
                       F=v["F"][j], F_lo=f_lo, F_hi=f_hi, best_variant=is_best,
                       best_gain=v["top_gain"] if is_best else np.nan, best_gain_lo=t_lo, best_gain_hi=t_hi,
                       w_human_mean=WMEAN[g][j] if c == "C3" else np.nan,
                       w_human_fold_sd=WSD[g][j] if c == "C3" else np.nan))
UP = pd.DataFrame(UP)
print(f"item 3 done {time.time() - T0:.0f}s", flush=True)


# ==================================================================== outputs: CSVs
LEAD.to_csv(CFG.DOCS / "amendment8_leaderboard.csv", index=False, float_format="%.6f")
AV.to_csv(CFG.DOCS / "amendment8_averaging.csv", index=False, float_format="%.6f")
UP.to_csv(CFG.DOCS / "amendment8_upgrade.csv", index=False, float_format="%.6f")


# ==================================================================== figures
COL = {"S": "#1b6ca8", "P": "#d1495b"}
fig, axes = plt.subplots(1, 2, figsize=(13, 8))
for ax, rule in zip(axes, RULES):
    sgn = -1 if rule == "log" else 1
    vm = sgn * LB[rule][:34]
    order = np.argsort(LB[rule][:34])[::-1]                 # best at the top
    ax.plot(vm[order], np.arange(34), "o", color="#5b5b5b", ms=4)
    ax.set_yticks(np.arange(34))
    ax.set_yticklabels([variants[j].replace(" with freeze values", "") for j in order], fontsize=6.5)
    for c, g in ((34, "P"), (35, "S")):
        rr = LEAD[(LEAD.rule == rule) & (LEAD.entry == f"{GNAME[g]} median")].iloc[0]
        ax.axvline(sgn * LB[rule][c], color=COL[g], lw=1.6,
                   label=f"{GNAME[g]} median (rank {rr['rank']} [{rr['rank_lo']:.0f}, {rr['rank_hi']:.0f}])")
        ax.axvline(sgn * IND[g][rule], color=COL[g], lw=1, ls=":",
                   label=f"{INDNAME[g]} (reference)")
    ax.set_xlabel(f"mean {RULE_NAME[rule]} on T ({'higher' if rule == 'log' else 'lower'} = better)")
    ax.set_title(RULE_NAME[rule])
    ax.legend(fontsize=7, loc="upper left" if rule == "log" else "upper right")
fig.suptitle(f"Amendment 8: the 34 matched variants and the human entries on T ({nT} targets, "
             f"{qT} questions); rank intervals: 95% question-cluster bootstrap", fontsize=10)
fig.tight_layout()
fig.savefig(CFG.FIGDIR / "a8_leaderboard.png", dpi=150)
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
for ax, rule in zip(axes, RULES):
    for g in GROUPS:
        for c, mk, off in (("C1", "o", -0.12), ("C3", "s", 0.12)):
            s = UP[(UP.group_median == g) & (UP.combiner == c) & (UP.rule == rule)]
            x = s["rank_m"] + off + (0.06 if g == "P" else -0.06)
            ax.errorbar(x, s["U"], yerr=[s["U"] - s["U_lo"], s["U_hi"] - s["U"]], fmt=mk, ms=4,
                        mfc=COL[g] if c == "C1" else "white", color=COL[g], ecolor=COL[g], elinewidth=.7,
                        capsize=0, label=f"{GNAME[g]} median, {c}{' (primary)' if c == 'C1' else ''}")
    ax.axhline(0, color="#999", lw=.8, ls="--")
    ax.set_xlabel(f"rank of m alone on T ({RULE_NAME[rule]}; 1 = best)")
    ax.set_ylabel("equivalent upgrade U = rank(m) − rank(m + g), places")
    ax.set_title(RULE_NAME[rule] + (" (primary)" if rule == "log" else ""))
    ax.legend(fontsize=7)
fig.suptitle("Amendment 8: equivalent model upgrade from adding a human median, held-out on T, "
             "95% question-cluster bootstrap intervals", fontsize=10)
fig.tight_layout()
fig.savefig(CFG.FIGDIR / "a8_upgrade.png", dpi=150)
plt.close(fig)


# ==================================================================== report
head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=CFG.REPO_ROOT).stdout.strip()
dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True,
                       cwd=CFG.REPO_ROOT).stdout.strip()


def ci(e, lo, hi, f):
    return f"{e:+{f}} [{lo:+{f}}, {hi:+{f}}]"


def fmt_score(x, rule):
    return f"{x:.3f}" if rule == "log" else f"{x:.2f}"


def short(m):
    return m.replace(" with freeze values", "")


lead_h = {(r.entry, r.rule): r for r in LEAD.itertuples()}
SR = {rule: (float(SPEAR[rule].statistic), float(SPEAR[rule].pvalue)) for rule in RULES}

w("# SPEC v3 Amendment 8: leaderboard levels and equivalent model upgrade")
w()
w(f"Spec: `{SPEC_COMMIT}` (specs/forecast_spec_v3.md, Amendment 8 with its pre-run clarifications, committed "
  f"before this code was written or run). Repo HEAD at run: `{head}`"
  + (" (working tree has uncommitted files: this script and its outputs)" if dirty else "")
  + ". No v1, v2, P5 or Amendment 6/7 number changes.")
w()
w("## |T|")
w()
w(f"- |T| = **{nT} targets on {qT} questions** (of 578 targets and 162 questions in the v1 H1 frame): targets where "
  f"all 34 variants have non-imputed forecasts and both group medians exist. Both medians exist on all 578 targets, "
  f"so T is the set where all 34 variants are non-imputed ({n_all34}). |T| ≥ 300, so the larger-set leaderboard is "
  "not required and is not reported.")
w()
w("## Reproduction check")
w()
w("Amendment 7's G_B(M1) recomputed on the Amendment 8 item 2 rows for M1 (every row where M1 is non-imputed; "
  "clarification 1). M1 has no imputed rows, so the row sets coincide with Amendment 7's. Same bootstrap draws "
  f"(seed {SEED}, {DRAWS} draws). Match tolerance: the 6 decimals stored in `docs/amendment7_pervariant.csv`.")
w()
w("| group | rows (A8 / A7) | Amendment 8 | Amendment 7 | match |")
w("|---|---|---|---|---|")
for g, r in REPRO.items():
    w(f"| {g} | {r['n']:,} / {r['n_ref']:,} | {ci(*r['got'], '.4f')} | {ci(*r['ref'], '.4f')} | "
      f"{'yes' if r['ok'] else 'NO'} |")
w()
w("## Setup")
w()
w(f"- Frame: `data/derived/full_frame.pkl` ({len(full):,} forecaster-target rows, 578 targets, {n_q} questions; "
  "v1 Amendment 2 exclusions). Variant forecasts: the 34 matched variants via the v1 loader, non-imputed only.")
w(f"- Scores: Brier ×100; log score with probabilities clipped to [{LO}, {HI}]. Leaderboard scores are reported as "
  "mean Brier ×100 (lower = better) and mean log score (higher = better). Every gain is a loss difference "
  "\"score(x) − score(y)\" with Brier and log loss as the losses, so positive means y is better. Log score is "
  "primary and Brier is beside it (clarification 3).")
w(f"- Intervals: question-level cluster bootstrap, {DRAWS} draws, seed {SEED}, percentile 95%; the draws are "
  "Amendment 7's, and one set serves every quantity in items 1–3. Questions with no target in T contribute "
  "nothing to an item 1 or item 3 draw.")
w(f"- Folds (item 3): Amendment 6's assignment (5 folds by question, seed {FOLD_SEED}, v2 cross-fit rule), assigned "
  "on all 578 targets and restricted to T, so each question keeps its Amendment 6 fold. In each bootstrap draw the "
  "folds are reassigned on the draw's clusters with the same rule and C3 is refit (clarification 4).")
w("- Combiners: C1 = (p + q)/2. C3 = w·g + (1 − w)·m, w ∈ [0, 1] on the human median, closed-form training-fold "
  "Brier minimum then clipped (Amendment 6 `fit_c3`), fit on T targets in the training folds and frozen on the "
  "test fold.")
w("- Two orderings (clarification 2). Selection-set Q (v1 §4 Brier on the 930-target selection set; the Figure 1 "
  "order) orders the three anchor variants and sets item 2's threshold. Score on T, separately per rule, orders "
  "variants for ranks, U, F and \"best variant\" in items 1 and 3. Spearman correlation between selection-set Q and "
  f"the score-on-T order: log score ρ = {SR['log'][0]:.3f}, Brier ρ = {SR['brier'][0]:.3f} (34 variants; both "
  "orderings are losses, so positive ρ means agreement).")
w("- Ranks: 1 + the number of the 34 variants with strictly lower mean loss on T (ties share the better rank).")
w()
w("Choices not fixed by the spec, made here and flagged:")
w(f"- Median-ranked anchor variant: 34 is even; the anchor is Q rank 17 ({short(variants[16])}).")
w("- F's denominator uses the best variant identified at the point estimate (per rule), held fixed across draws; "
  "U is recomputed from re-ranked variants in every draw. For variants whose loss is close to the best variant's, "
  "F's denominator is near zero and its interval is wide or unbounded; those intervals are reported as computed.")
w(f"- C3 weight-stability rule applied over all 68 (variant, median) pairs: C3 is descriptive only if any of them "
  f"has a fold-to-fold weight SD above {SD_RULE}.")
w(f"- Item 2 \"share of forecasters helped\" uses each forecaster's own mean of score(m) − score(A) over their rows "
  f"for m (at least {MIN_ROWS}), per rule; no interval (none specified).")
w("- Item 2 threshold X: the best Q rank whose gain-over-AI interval lies entirely above zero. Variants with worse Q "
  "rank whose interval does not lie above zero are listed as exceptions, since the sentence \"at or below rank X\" "
  "claims all of them.")
w()
w("## Locked reading (restated)")
w()
w("- All three items are descriptive readouts for Section 10. No new hypothesis test, no per-variant p-values. "
  "34 variants are not 34 tests.")
w("- Recorded expectation (before the run): the superforecaster median ranks above every variant; the public median "
  "ranks in the lower half; averaging helps the public against weaker models only; for the public median, U is near "
  "zero for the top variant and positive for low-ranked variants.")
w("- If log score and Brier disagree on a readout, report both and state the disagreement in one sentence.")
w()

# ---- expectation check
w("## Recorded expectation, checked")
w()
for rule in RULES:
    s = lead_h[("superforecaster median", rule)]
    p = lead_h[("public median", rule)]
    w(f"- {RULE_NAME[rule]}: superforecaster median rank {s.rank} [{s.rank_lo:.0f}, {s.rank_hi:.0f}] of 35 "
      f"({'above every variant; expectation met' if s.rank == 1 else 'not above every variant; expectation not met'}); public median rank {p.rank} "
      f"[{p.rank_lo:.0f}, {p.rank_hi:.0f}] of 35 ({'lower half; expectation met' if p.rank >= 18 else 'upper half; expectation not met'}; lower half = "
      "rank 18–35).")
for rule in RULES:
    th = THR[("P", rule)]
    if th["X"] is None:
        w(f"- {RULE_NAME[rule]}: averaging does not help the public against any variant (no interval entirely above zero).")
    else:
        w(f"- {RULE_NAME[rule]}: averaging helps the public (interval above zero) against {th['n_pos']} of 34 variants; "
          f"the best Q rank among them is {th['X']}"
          + (f"; {len(th['exceptions'])} variants at worse Q ranks do not have an interval above zero" if th["exceptions"]
             else "; every variant at that Q rank or worse has an interval above zero") + ".")
for rule in RULES:
    v = R3[("P", "C1", rule)]
    b = BEST[rule]
    low = [j for j in range(34) if v["rank_m"][j] > 27]
    w(f"- {RULE_NAME[rule]}, public median, C1: U for the top variant on T ({short(variants[b])}) = {v['U'][b]:+d} "
      f"[{V.pct_ci(BU[('P', 'C1', rule)][:, b])[0]:+.0f}, {V.pct_ci(BU[('P', 'C1', rule)][:, b])[1]:+.0f}]; "
      f"U for the 7 lowest-ranked variants on T (ranks 28–34): "
      + ", ".join(f"{v['U'][j]:+d}" for j in sorted(low, key=lambda j: v["rank_m"][j])) + ".")
w()

# ---- rule disagreements
dis = []
for g in GROUPS:
    a, b = lead_h[(f"{GNAME[g]} median", "log")], lead_h[(f"{GNAME[g]} median", "brier")]
    if a.rank != b.rank:
        dis.append(f"Item 1: the {GNAME[g]} median ranks {a.rank} under log score and {b.rank} under Brier.")
    ta, tb = THR[(g, "log")]["X"], THR[(g, "brier")]["X"]
    if ta != tb:
        dis.append(f"Item 2: the {GNAME[g]} threshold rank X is {ta} under log score and {tb} under Brier.")
for g in GROUPS:
    for j in (0, 16, 33):
        ua, ub = R3[(g, "C1", "log")]["U"][j], R3[(g, "C1", "brier")]["U"][j]
        if np.sign(ua) != np.sign(ub):
            dis.append(f"Item 3: for the {GNAME[g]} median with anchor {short(variants[j])} (C1), U is {ua:+d} under "
                       f"log score and {ub:+d} under Brier.")
if BEST["log"] != BEST["brier"]:
    dis.append(f"Best variant on T: {short(variants[BEST['log']])} under log score, {short(variants[BEST['brier']])} "
               "under Brier.")
w("## Log score and Brier disagreements")
w()
if dis:
    for s in dis:
        w(f"- {s}")
else:
    w("- None on the human-median ranks, the item 2 thresholds, the sign of U at the three anchors, or the best variant.")
w()

# ---- item 1
w("## Item 1. Leaderboard of levels on T (researcher)")
w()
w(f"Entries scored on T ({nT} targets). Human medians: rank among the 34 variants plus the entry, with 95% bootstrap "
  "rank interval. Mean individual forecasters are a reference line only (mean over that group's forecaster-target "
  f"rows on T: S {IND['S']['n_rows']:,} rows, P {IND['P']['n_rows']:,} rows); their rank is shown for orientation, "
  "without an interval.")
w()
w("| entry | log score | rank [95% CI] | Brier ×100 | rank [95% CI] |")
w("|---|---|---|---|---|")
for e in ("superforecaster median", "public median"):
    a, b = lead_h[(e, "log")], lead_h[(e, "brier")]
    w(f"| {e} | {a.score:.3f} | {a.rank} [{a.rank_lo:.0f}, {a.rank_hi:.0f}] | {b.score:.2f} | "
      f"{b.rank} [{b.rank_lo:.0f}, {b.rank_hi:.0f}] |")
for g in GROUPS:
    e = INDNAME[g]
    a, b = lead_h[(e, "log")], lead_h[(e, "brier")]
    w(f"| {e} (reference) | {a.score:.3f} | ({a.rank}) | {b.score:.2f} | ({b.rank}) |")
w()
w("The 34 variants on T, in selection-set Q order:")
w()
w("| Q rank | variant | Q | log score | rank on T | Brier ×100 | rank on T |")
w("|---|---|---|---|---|---|---|")
for j, m in enumerate(variants):
    a, b = lead_h[(m, "log")], lead_h[(m, "brier")]
    w(f"| {j + 1} | {short(m)} | {Qv[j]:.4f} | {a.score:.3f} | {a.rank} | {b.score:.2f} | {b.rank} |")
w()
w("![Amendment 8 leaderboard](figures/a8_leaderboard.png)")
w()

# ---- item 2
w("## Item 2. Averaging rule for an individual (person)")
w()
w("A = (h + m)/2 for each forecaster-target row where m is non-imputed (clarification 1). Gain vs AI = score(m) − "
  "score(A); gain vs own = score(h) − score(A); positive = averaging is better. Log gains in natural units, Brier ×100.")
w()
w("Threshold readout (Q rank; \"averaging your forecast with the model helps against models at or below rank X\"):")
w()
w("| group | rule | X | variant at X | variants with interval above zero | exceptions at worse Q ranks |")
w("|---|---|---|---|---|---|")
for g in GROUPS:
    for rule in RULES:
        th = THR[(g, rule)]
        if th["X"] is None:
            w(f"| {g} | {RULE_NAME[rule]} | none | no variant has an interval entirely above zero | 0 | – |")
        else:
            w(f"| {g} | {RULE_NAME[rule]} | {th['X']} | {short(th['variant'])} | {th['n_pos']} | "
              f"{', '.join(short(x) for x in th['exceptions']) or 'none'} |")
w()
for g in GROUPS:
    w(f"### {HEAD[g]}")
    w()
    w("| Q rank | variant | n rows | gain vs AI, log [95% CI] | gain vs own, log [95% CI] | helped, log (n) | "
      "gain vs AI, Brier ×100 [95% CI] | gain vs own, Brier ×100 [95% CI] | helped, Brier (n) |")
    w("|---|---|---|---|---|---|---|---|---|")
    for _, r in AV[AV["group"] == g].sort_values("Q_rank").iterrows():
        w(f"| {r['Q_rank']} | {short(r['variant'])} | {r['n_rows']:,} | "
          f"{ci(r['gain_vs_ai_log'], r['gain_vs_ai_log_lo'], r['gain_vs_ai_log_hi'], '.3f')} | "
          f"{ci(r['gain_vs_own_log'], r['gain_vs_own_log_lo'], r['gain_vs_own_log_hi'], '.3f')} | "
          f"{r['share_helped_log']:.2f} ({r['n_forecasters_log']}) | "
          f"{ci(r['gain_vs_ai_brier'], r['gain_vs_ai_brier_lo'], r['gain_vs_ai_brier_hi'], '.2f')} | "
          f"{ci(r['gain_vs_own_brier'], r['gain_vs_own_brier_lo'], r['gain_vs_own_brier_hi'], '.2f')} | "
          f"{r['share_helped_brier']:.2f} ({r['n_forecasters_brier']}) |")
    w()

# ---- item 3
w("## Item 3. Equivalent model upgrade (institution)")
w()
w(f"Held-out scores on T (5-fold out-of-fold predictions; C1 needs no fit). The m + g scores are on the {nT} targets "
  "in T, not Amendment 6's 578, so they are not expected to reproduce Amendment 6 (clarification 5).")
w()
mx = max(WSD[g].max() for g in GROUPS)
w(f"- C3 weight-stability rule: {'at least one' if sd_flag else 'no'} (variant, median) pair has a fold-to-fold SD "
  f"of the human weight above {SD_RULE} (max {mx:.3f}), so C3 is "
  f"{'descriptive only and C1 carries the readout' if sd_flag else 'not restricted by the rule'}.")
for rule in RULES:
    b = BEST[rule]
    w(f"- Best variant on T, {RULE_NAME[rule]}: {short(variants[b])} (Q rank {b + 1}).")
w()
w("Anchor variants (selection-set Q: top, median, bottom), C1 primary:")
w()
w("| median g | anchor | rule | rank m | rank m + g | U [95% CI] | F [95% CI] or best-variant gain |")
w("|---|---|---|---|---|---|---|")
for g in GROUPS:
    for j, lab in ((0, "top"), (16, "median"), (33, "bottom")):
        for rule in RULES:
            r = UP[(UP.variant == variants[j]) & (UP.group_median == g) & (UP.combiner == "C1") & (UP.rule == rule)].iloc[0]
            ftxt = (f"best-variant gain {ci(r['best_gain'], r['best_gain_lo'], r['best_gain_hi'], '.3f' if rule == 'log' else '.2f')}"
                    if r["best_variant"] else ci(r["F"], r["F_lo"], r["F_hi"], ".2f"))
            w(f"| {GNAME[g]} | {lab}: {short(variants[j])} | {RULE_NAME[rule]} | {r['rank_m']} | {r['rank_m_plus_g']} | "
              f"{r['U']:+d} [{r['U_lo']:+.0f}, {r['U_hi']:+.0f}] | {ftxt} |")
w()
for g in GROUPS:
    for rule in RULES:
        w(f"### {GNAME[g].capitalize()} median, {RULE_NAME[rule]}{' (primary)' if rule == 'log' else ''}")
        w()
        w("| Q rank | variant | score m | rank m | C1: score m + g | rank | U [95% CI] | F [95% CI] | "
          "C3: score m + g | rank | U [95% CI] | F [95% CI] | C3 w(human) mean (fold SD) |")
        w("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for j, m in enumerate(variants):
            r1 = UP[(UP.variant == m) & (UP.group_median == g) & (UP.combiner == "C1") & (UP.rule == rule)].iloc[0]
            r3 = UP[(UP.variant == m) & (UP.group_median == g) & (UP.combiner == "C3") & (UP.rule == rule)].iloc[0]
            def ftx(r):
                if r["best_variant"]:
                    return "best: " + ci(r["best_gain"], r["best_gain_lo"], r["best_gain_hi"], ".3f" if rule == "log" else ".2f")
                return ci(r["F"], r["F_lo"], r["F_hi"], ".2f")
            w(f"| {j + 1} | {short(m)} | {fmt_score(r1['score_m'], rule)} | {r1['rank_m']} | "
              f"{fmt_score(r1['score_m_plus_g'], rule)} | {r1['rank_m_plus_g']} | "
              f"{r1['U']:+d} [{r1['U_lo']:+.0f}, {r1['U_hi']:+.0f}] | {ftx(r1)} | "
              f"{fmt_score(r3['score_m_plus_g'], rule)} | {r3['rank_m_plus_g']} | "
              f"{r3['U']:+d} [{r3['U_lo']:+.0f}, {r3['U_hi']:+.0f}] | {ftx(r3)} | "
              f"{r3['w_human_mean']:.2f} ({r3['w_human_fold_sd']:.3f}) |")
        w()
w("![Amendment 8 upgrade](figures/a8_upgrade.png)")
w()
w("All numbers: `docs/amendment8_leaderboard.csv`, `docs/amendment8_averaging.csv`, `docs/amendment8_upgrade.csv`. "
  "Rows dropped for imputed forecasts in item 2, per variant: "
  + ", ".join(f"{short(m)} {int(AV[(AV.variant == m)]['rows_dropped_imputed'].iloc[0])}" for m in variants
              if AV[AV.variant == m]["rows_dropped_imputed"].iloc[0]) + ".")
w()
w(f"Runtime {time.time() - T0:.0f}s.")
(CFG.DOCS / "amendment8_REPORT.md").write_text("\n".join(OUT) + "\n")
print("wrote docs/amendment8_REPORT.md", flush=True)
