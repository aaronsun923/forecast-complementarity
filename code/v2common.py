"""Shared machinery for SPEC v2 (benchmark-quality curve).

Stage 1 (per variant) reuses the v1 code path unchanged:
  beta  -> models.encompassing      (v1 H2)
  eps   -> models.fit_spec          (v1 H4, group-only)
Stage 2 and the two bootstraps are new, as the v2 feasibility audit set out.

`fast_logit` is a numpy IRLS with a cluster-robust sandwich used ONLY inside the
H6 bootstrap, where the v1 path would be too slow. It is validated against
models.encompassing at run time and the agreement is reported.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

import config as CFG
import fbdata as F
import models as M

Z1 = 1.959963985
ZCOLS = ["DIS", "CONF_a", "logHZ", "EXT_a", "absD_a"]
# v1 H4 formula, group-only (GRP drops out within a group)
F4_GROUP = ("G_a ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + MKT "
            "+ EXT_a_z:DIS_z")


def se_from_ci(lo, hi):
    """Both v1 helpers expose normal-based intervals but no SE."""
    return (hi - lo) / (2 * Z1)


def logit_clip(p, clip=CFG.CLIP):
    q = np.clip(p, clip[0], clip[1])
    return np.log(q / (1 - q))


# ----------------------------------------------------------------- stage 1
def build_variant_table(hum, mods, meta, rank, test_targets):
    """Q_m, scaffold/base labels, and imputed target counts per variant."""
    imp = (mods[mods["target"].isin(test_targets)]
           .groupby("model")["imputed"]
           .agg(imputed_targets="sum", targets_available="size"))
    tab = (rank[["brier"]].rename(columns={"brier": "Q_m"})
           .join(meta.set_index("model")[["base", "scaffold"]])
           .join(imp))
    tab["targets_kept"] = tab["targets_available"] - tab["imputed_targets"]
    return tab.sort_values("Q_m")


def target_level(frame):
    """Target-level frame for the encompassing fits (v1 H2 shape)."""
    tl = (frame.groupby("target")
          .agg(o=("o", "first"), p_a=("p_a", "first"), question=("question", "first"))
          .reset_index())
    for g, name in (("S", "p_h_S"), ("P", "p_h_P")):
        med = frame[frame.GRP == g].groupby("target")["p_h"].median().rename(name)
        tl = tl.merge(med, on="target", how="left")
    return tl


def stage1_variant(hum, mods, stats, model_name, pilot_questions=None):
    """beta and eps for one variant, both groups, via the v1 code path."""
    fr, info = F.build_frame(hum, mods, stats, model_name)
    if pilot_questions is not None:
        fr = fr[fr["question"].isin(pilot_questions)].copy()
    out = {"rows": len(fr), "targets": fr["target"].nunique(),
           "questions": fr["question"].nunique(),
           "rows_dropped_pa_imputed": info["rows_dropped_pa_imputed"]}

    tl = target_level(fr)
    out["targets_tl"] = len(tl)
    for g, col in (("S", "p_h_S"), ("P", "p_h_P")):
        r = M.encompassing(tl, col, CFG.CLIP)
        b = float(r["params"]["human_minus_model"])
        lo, hi = (float(r["ci"].loc["human_minus_model", 0]),
                  float(r["ci"].loc["human_minus_model", 1]))
        out[f"beta_{g}"] = b
        out[f"beta_{g}_lo"], out[f"beta_{g}_hi"] = lo, hi
        out[f"beta_{g}_se"] = se_from_ci(lo, hi)
        out[f"beta_{g}_clipped_human"] = r["clipped_human"]

    for g in ("S", "P"):
        sub = fr[fr.GRP == g].copy()
        for c in ZCOLS:
            sub[c + "_z"] = F.zscore(sub[c])
        res, fb = M.fit_spec(F4_GROUP, sub, "H4")
        e = float(res.params["EXT_a_z"])
        lo, hi = (float(res.ci.loc["EXT_a_z", 0]), float(res.ci.loc["EXT_a_z", 1]))
        out[f"eps_{g}"] = e
        out[f"eps_{g}_lo"], out[f"eps_{g}_hi"] = lo, hi
        out[f"eps_{g}_se"] = se_from_ci(lo, hi)
        out[f"eps_{g}_kind"] = res.kind
        out[f"eps_{g}_fallback"] = fb
        out[f"eps_{g}_rows"] = len(sub)
        # G_m,g: mean human gain over this variant (SPEC 3, near-identity)
        out[f"G_{g}"] = float(sub["G_a"].mean())
    return out


# ------------------------------------------------- fast logistic (bootstrap)
def fast_logit(X, y, groups, maxit=60, tol=1e-10):
    """IRLS + cluster-robust sandwich; matches statsmodels Logit(cov_type=cluster,
    use_correction=True). Returns (coef, se) or (None, None) on failure."""
    n, k = X.shape
    b = np.zeros(k)
    for _ in range(maxit):
        p = 1.0 / (1.0 + np.exp(-(X @ b)))
        W = p * (1 - p)
        H = (X * W[:, None]).T @ X
        try:
            step = np.linalg.solve(H, X.T @ (y - p))
        except np.linalg.LinAlgError:
            return None, None
        b = b + step
        if not np.all(np.isfinite(b)):
            return None, None
        if np.max(np.abs(step)) < tol:
            break
    p = 1.0 / (1.0 + np.exp(-(X @ b)))
    W = p * (1 - p)
    try:
        Hinv = np.linalg.inv((X * W[:, None]).T @ X)
    except np.linalg.LinAlgError:
        return None, None
    u = X * (y - p)[:, None]
    uid, inv = np.unique(groups, return_inverse=True)
    G = len(uid)
    if G < 2:
        return None, None
    S = np.zeros((k, k))
    for gi in range(G):
        s = u[inv == gi].sum(0)
        S += np.outer(s, s)
    V = Hinv @ S @ Hinv * (G / (G - 1)) * ((n - 1) / (n - k))
    d = np.diag(V)
    if np.any(d <= 0) or not np.all(np.isfinite(d)):
        return None, None
    return b, np.sqrt(d)


# ----------------------------------------------------------------- stage 2
def wls_slope(q, y, se, base):
    """Inverse-variance WLS of y on q with base-model-clustered SEs."""
    w = 1.0 / np.asarray(se) ** 2
    X = sm.add_constant(np.asarray(q))
    m = sm.WLS(np.asarray(y), X, weights=w).fit()
    mc = sm.WLS(np.asarray(y), X, weights=w).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(np.asarray(base))[0]})
    ci = mc.conf_int()
    # WLS leverage / Cook's D by hand: statsmodels' get_influence is OLS-only here.
    # Work in the whitened space, X~ = sqrt(w) X, y~ = sqrt(w) y.
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    k = Xw.shape[1]
    XtXi = np.linalg.pinv(Xw.T @ Xw)
    lev = np.einsum("ij,jk,ik->i", Xw, XtXi, Xw)          # diag of the hat matrix
    rw = np.asarray(m.resid) * sw                          # whitened residuals
    s2 = float(rw @ rw) / (len(y) - k)
    denom = np.clip((1.0 - lev) ** 2, 1e-12, None)
    cooks = (rw ** 2 / (k * s2)) * lev / denom
    return dict(intercept=float(mc.params[0]), slope=float(mc.params[1]),
                slope_se=float(mc.bse[1]),
                slope_lo=float(ci[1][0]), slope_hi=float(ci[1][1]),
                n=int(len(y)), n_clusters=int(pd.Series(base).nunique()),
                resid=np.asarray(m.resid), fitted=np.asarray(m.fittedvalues),
                weights=w, leverage=lev, cooks=cooks, model=m)


def zero_crossing(intercept, slope):
    if slope == 0 or not np.isfinite(slope):
        return np.nan
    return -intercept / slope


# --------------------------------------------------- H6 question bootstrap
def boot_h6(tl_wide, variants, qtab, group, draws, seed, clip=CFG.CLIP):
    """SPEC 4 [LOCKED]: resample the pilot's questions with replacement, recompute
    every beta_m on the resampled data, refit the stage-2 slope. Q_m is held fixed.
    Both beta and its SE are recomputed inside each draw, so the inverse-variance
    weights are the draw's own.
    """
    rng = np.random.default_rng(seed)
    qs = tl_wide["question"].unique()
    idx_by_q = {q: np.flatnonzero(tl_wide["question"].values == q) for q in qs}
    lh = logit_clip(tl_wide[f"p_h_{group}"].values, clip)
    y_all = tl_wide["o"].values.astype(float)
    LM = {m: logit_clip(tl_wide[m].values, clip) for m in variants}
    ok_all = {m: np.isfinite(tl_wide[m].values) for m in variants}
    q_of = np.asarray([qtab.loc[m, "Q_m"] for m in variants])
    base_of = np.asarray([qtab.loc[m, "base"] for m in variants])

    slopes, inters, crossings = [], [], []
    n_fail_fit, n_fail_draw = 0, 0
    for _ in range(draws):
        pick = rng.choice(qs, size=len(qs), replace=True)
        rows, clus = [], []
        for j, q in enumerate(pick):
            r = idx_by_q[q]
            rows.append(r)
            clus.append(np.full(len(r), j))          # duplicated questions = distinct clusters
        rows = np.concatenate(rows); clus = np.concatenate(clus)
        yb = y_all[rows]; lhb = lh[rows]
        bs, ses, qs_, bases_ = [], [], [], []
        for k, m in enumerate(variants):
            keep = ok_all[m][rows]
            if keep.sum() < 20:
                n_fail_fit += 1
                continue
            la = LM[m][rows][keep]
            X = np.column_stack([np.ones(keep.sum()), la, lhb[keep] - la])
            b, se = fast_logit(X, yb[keep], clus[keep])
            if b is None or se[2] <= 0 or not np.isfinite(se[2]):
                n_fail_fit += 1
                continue
            bs.append(b[2]); ses.append(se[2]); qs_.append(q_of[k]); bases_.append(base_of[k])
        if len(bs) < 5 or len(set(bases_)) < 2:
            n_fail_draw += 1
            continue
        w = 1.0 / np.asarray(ses) ** 2
        X2 = sm.add_constant(np.asarray(qs_))
        try:
            fit = sm.WLS(np.asarray(bs), X2, weights=w).fit()
        except Exception:                                    # noqa: BLE001
            n_fail_draw += 1
            continue
        inters.append(float(fit.params[0])); slopes.append(float(fit.params[1]))
        crossings.append(zero_crossing(fit.params[0], fit.params[1]))
    return dict(slopes=np.array(slopes), intercepts=np.array(inters),
                crossings=np.array(crossings),
                n_draws_used=len(slopes), n_fail_draw=n_fail_draw,
                n_fail_fit=n_fail_fit)


# ----------------------------------------- H7 wild cluster bootstrap (stage 2)
def wild_cluster_boot(q, y, se, base, draws, seed):
    """SPEC 4 [LOCKED]: Rademacher wild cluster bootstrap over base models,
    applied to the precomputed eps points. Conditions on stage 1."""
    rng = np.random.default_rng(seed)
    w = 1.0 / np.asarray(se) ** 2
    X = sm.add_constant(np.asarray(q))
    fit = sm.WLS(np.asarray(y), X, weights=w).fit()
    resid = np.asarray(fit.resid); fitted = np.asarray(fit.fittedvalues)
    codes, uniq = pd.factorize(np.asarray(base))
    slopes, inters = [], []
    for _ in range(draws):
        sgn = rng.choice([-1.0, 1.0], size=len(uniq))[codes]
        ystar = fitted + resid * sgn
        try:
            f = sm.WLS(ystar, X, weights=w).fit()
        except Exception:                                    # noqa: BLE001
            continue
        inters.append(float(f.params[0])); slopes.append(float(f.params[1]))
    return dict(slopes=np.array(slopes), intercepts=np.array(inters),
                n_draws_used=len(slopes), n_clusters=len(uniq))


def pct_ci(a, lo=2.5, hi=97.5):
    a = np.asarray(a)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return np.nan, np.nan
    return float(np.percentile(a, lo)), float(np.percentile(a, hi))
