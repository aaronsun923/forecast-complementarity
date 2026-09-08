"""Extra machinery for the SPEC v2 full run under Amendment 1.

New here relative to v2common (which the pilot used and which is left untouched):
  * fast_eps          - Amendment 1 item 2 inner-loop estimator for eps:
                        OLS with forecaster fixed effects absorbed by within-
                        demeaning, question-clustered SEs. This is the estimator
                        SPEC v1 Sec 5 / v1 Amendment 1 D.1 already sanction.
  * boot_questions_*  - the single question-level cluster bootstrap of SPEC v2
                        Sec 4, applied to beta, to eps, and to the Sec 6 item 4
                        cross-fitted log-score gain. Each stores the full
                        per-draw (estimate, SE) matrix so that every stage-2
                        variation (robustness 1, 2 and 3) is a refit on the same
                        draws rather than a fresh bootstrap.
  * flag_amendment1   - the LOCKED leverage rule: h > 2p/n or Cook's D > 4/n.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

import config as CFG
import fbdata as F
import v2common as V

COVS = ["EXT_a_z", "absD_a_z", "DIS_z", "CONF_a_z", "logHZ_z", "MKT", "EXTxDIS"]


def prep_group(sub):
    """z-score the continuous covariates on this subset and build the interaction."""
    d = sub.copy()
    for c in V.ZCOLS:
        d[c + "_z"] = F.zscore(d[c])
    d["EXTxDIS"] = d["EXT_a_z"] * d["DIS_z"]
    return d


def _zs(a):
    s = a.std()
    return (a - a.mean()) / s if s > 0 else a * 0.0


# ------------------------------------------------- Amendment 1 item 2 estimator
def fast_eps(y, X, fe, clus):
    """OLS with forecaster FE absorbed, question-clustered SE.
    Returns (coef vector, se vector) on the COVS design, or (None, None)."""
    fe = np.asarray(fe)
    n_fe = int(fe.max()) + 1
    cnt = np.bincount(fe, minlength=n_fe).astype(float)
    cnt[cnt == 0] = 1.0

    def dm(v):
        s = np.bincount(fe, weights=v, minlength=n_fe)
        return v - (s / cnt)[fe]

    yd = dm(y)
    Xd = np.column_stack([dm(X[:, j]) for j in range(X.shape[1])])
    XtX = Xd.T @ Xd
    try:
        b = np.linalg.solve(XtX, Xd.T @ yd)
        XtXi = np.linalg.inv(XtX)
    except np.linalg.LinAlgError:
        return None, None
    r = yd - Xd @ b
    u = Xd * r[:, None]
    uid, inv = np.unique(clus, return_inverse=True)
    G = len(uid)
    if G < 2:
        return None, None
    k = Xd.shape[1]
    S = np.zeros((k, k))
    for g in range(G):
        S += np.outer(u[inv == g].sum(0), u[inv == g].sum(0))
    n = len(y)
    dfk = k + n_fe
    if n - dfk <= 0:
        return None, None
    Vc = XtXi @ S @ XtXi * (G / (G - 1)) * ((n - 1) / (n - dfk))
    d = np.diag(Vc)
    if np.any(d <= 0) or not np.all(np.isfinite(d)):
        return None, None
    return b, np.sqrt(d)


# ------------------------------------------------------ per-group row bundles
def build_row_bundle(hum, mods, stats, variants, qmap, ycol="G_a", frames=None):
    """Pre-extract, per variant and group, the arrays fast_eps needs.

    `qmap` maps question -> a GLOBAL integer code, so a bootstrap draw's question
    picks line up across variants even though variants drop different targets.
    `raw` holds the UNSTANDARDISED covariates so each draw re-standardises.
    """
    bundle = {}
    for m in variants:
        fr = frames[m] if frames is not None else F.build_frame(hum, mods, stats, m)[0]
        for g in ("S", "P"):
            sub = fr[fr.GRP == g]
            bundle[(m, g)] = dict(
                qid=sub["question"].map(qmap).to_numpy(np.int32),
                fid=pd.factorize(sub["forecaster"])[0].astype(np.int32),
                y=sub[ycol].to_numpy(float),
                raw=np.column_stack([sub[c].to_numpy(float) for c in V.ZCOLS]),
                mkt=sub["MKT"].to_numpy(float))
    return bundle


def combo_quality(human_targets):
    """Sec 6 item 1: Q measured on the round's COMBINATION-question targets."""
    import json
    recs = []
    for path in sorted(CFG.MODEL_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        base, scaffold = F.parse_model(d["model"])
        if scaffold not in CFG.MATCHED_SCAFFOLDS:
            continue
        for x in d["forecasts"]:
            if not isinstance(x["id"], list):
                continue
            recs.append((d["model"], float(x["forecast"]), bool(x.get("imputed", False)),
                         bool(x["resolved"]), float(x["resolved_to"])))
    df = pd.DataFrame.from_records(
        recs, columns=["model", "p", "imputed", "resolved", "resolved_to"])
    ok = df[df["resolved"] & ~df["imputed"]].copy()
    ok["bs"] = (ok["p"] - ok["resolved_to"]) ** 2
    return ok.groupby("model")["bs"].agg(Q_combo="mean", n_combo="size")


def _design(raw, mkt, rows=None):
    """Standardise on the supplied rows, then build the COVS design."""
    r = raw if rows is None else raw[rows]
    k = mkt if rows is None else mkt[rows]
    z = np.column_stack([_zs(r[:, j]) for j in range(r.shape[1])])
    # ZCOLS order: DIS, CONF_a, logHZ, EXT_a, absD_a
    DIS, CONF, LHZ, EXT, ABS = z[:, 0], z[:, 1], z[:, 2], z[:, 3], z[:, 4]
    return np.column_stack([EXT, ABS, DIS, CONF, LHZ, k, EXT * DIS])


def eps_point(bundle_entry):
    """fast_eps on the full sample for one (variant, group)."""
    b = bundle_entry
    X = _design(b["raw"], b["mkt"])
    return fast_eps(b["y"], X, b["fid"], b["qid"])


# ------------------------------------------------- the question-level bootstrap
def _question_index(qid, n_q):
    return [np.flatnonzero(qid == q) for q in range(n_q)]


def boot_questions_eps(bundle, variants, groups, n_q, draws, seed, progress=None):
    """SPEC v2 Sec 4 bootstrap applied to eps via fast_eps (Amendment 1 item 2).
    Stores the full per-draw (eps, SE) matrix for every variant."""
    rng = np.random.default_rng(seed)
    idx = {k: _question_index(bundle[k]["qid"], n_q) for k in bundle}
    E = {g: np.full((draws, len(variants)), np.nan) for g in groups}
    Sd = {g: np.full((draws, len(variants)), np.nan) for g in groups}
    fails = 0
    for t in range(draws):
        pick = rng.integers(0, n_q, n_q)
        for g in groups:
            for vi, m in enumerate(variants):
                b = bundle[(m, g)]
                rows = np.concatenate([idx[(m, g)][q] for q in pick])
                clus = np.concatenate([np.full(len(idx[(m, g)][q]), j)
                                       for j, q in enumerate(pick)])
                if len(rows) < 50:
                    fails += 1
                    continue
                X = _design(b["raw"], b["mkt"], rows)
                co, se = fast_eps(b["y"][rows], X, b["fid"][rows], clus)
                if co is None or se[0] <= 0:
                    fails += 1
                    continue
                E[g][t, vi] = co[0]
                Sd[g][t, vi] = se[0]
        if progress and (t + 1) % progress == 0:
            print(f"    eps boot {t+1}/{draws}", flush=True)
    return dict(E=E, SE=Sd, fails=fails)


def boot_questions_beta(tl_wide, variants, groups, draws, seed, clip=CFG.CLIP,
                        progress=None):
    """SPEC v2 Sec 4 bootstrap for beta. Stores per-draw (beta, SE) matrices."""
    rng = np.random.default_rng(seed)
    qcodes, quniq = pd.factorize(tl_wide["question"])
    n_q = len(quniq)
    idx = _question_index(qcodes, n_q)
    y_all = tl_wide["o"].to_numpy(float)
    LH = {g: V.logit_clip(tl_wide[f"p_h_{g}"].to_numpy(float), clip) for g in groups}
    LM, OK = {}, {}
    for m in variants:
        v = tl_wide[m].to_numpy(float)
        LM[m] = V.logit_clip(v, clip)
        OK[m] = np.isfinite(v)
    B = {g: np.full((draws, len(variants)), np.nan) for g in groups}
    Sd = {g: np.full((draws, len(variants)), np.nan) for g in groups}
    fails = 0
    for t in range(draws):
        pick = rng.integers(0, n_q, n_q)
        rows = np.concatenate([idx[q] for q in pick])
        clus = np.concatenate([np.full(len(idx[q]), j) for j, q in enumerate(pick)])
        yb = y_all[rows]
        for g in groups:
            lhb = LH[g][rows]
            for vi, m in enumerate(variants):
                keep = OK[m][rows]
                if keep.sum() < 20:
                    fails += 1
                    continue
                la = LM[m][rows][keep]
                X = np.column_stack([np.ones(keep.sum()), la, lhb[keep] - la])
                co, se = V.fast_logit(X, yb[keep], clus[keep])
                if co is None or se[2] <= 0:
                    fails += 1
                    continue
                B[g][t, vi] = co[2]
                Sd[g][t, vi] = se[2]
        if progress and (t + 1) % progress == 0:
            print(f"    beta boot {t+1}/{draws}", flush=True)
    return dict(E=B, SE=Sd, fails=fails)


# ------------------------------------- Sec 6 item 4: cross-fitted log-score gain
def crossfit_gain(y, la, lh, qcodes, n_folds=5, seed=20260908, clip=CFG.CLIP):
    """Out-of-sample mean log-score improvement from adding the human term,
    cross-fitted in folds by question. Returns (gain, se) with the SE from the
    question-clustered mean of the per-target differences."""
    rng = np.random.default_rng(seed)
    quniq = np.unique(qcodes)
    fold_of_q = {q: i % n_folds for i, q in enumerate(rng.permutation(quniq))}
    folds = np.array([fold_of_q[q] for q in qcodes])
    d = np.full(len(y), np.nan)
    XA = np.column_stack([np.ones(len(y)), la])
    XB = np.column_stack([np.ones(len(y)), la, lh - la])
    for f in range(n_folds):
        tr, te = folds != f, folds == f
        if tr.sum() < 30 or te.sum() == 0:
            continue
        ba, _ = V.fast_logit(XA[tr], y[tr], qcodes[tr])
        bb, _ = V.fast_logit(XB[tr], y[tr], qcodes[tr])
        if ba is None or bb is None:
            return None, None
        pa = 1 / (1 + np.exp(-(XA[te] @ ba)))
        pb = 1 / (1 + np.exp(-(XB[te] @ bb)))
        lo, hi = clip
        pa = np.clip(pa, lo, hi); pb = np.clip(pb, lo, hi)
        yy = y[te]
        d[te] = (np.log(np.where(yy == 1, pb, 1 - pb))
                 - np.log(np.where(yy == 1, pa, 1 - pa)))
    ok = np.isfinite(d)
    if ok.sum() < 30:
        return None, None
    dd, qq = d[ok], qcodes[ok]
    gain = float(dd.mean())
    uid, inv = np.unique(qq, return_inverse=True)
    G = len(uid)
    if G < 2:
        return None, None
    sums = np.array([dd[inv == g].sum() for g in range(G)])
    n = len(dd)
    var = ((sums - n / G * gain) ** 2).sum() * G / (G - 1) / n ** 2
    se = float(np.sqrt(max(var, 1e-18)))
    return gain, se


# --------------------------------------------------- stage 2 on stored draws
def stage2(q, y, se, base):
    return V.wls_slope(np.asarray(q), np.asarray(y), np.asarray(se), np.asarray(base))


def stage2_draws(E, SE, q, mask=None):
    """Refit the stage-2 slope in every stored draw. Returns slopes, intercepts."""
    q = np.asarray(q, float)
    keep_v = np.ones(E.shape[1], bool) if mask is None else np.asarray(mask, bool)
    sl, ic, cr = [], [], []
    for t in range(E.shape[0]):
        e, s = E[t], SE[t]
        ok = keep_v & np.isfinite(e) & np.isfinite(s) & (s > 0)
        if ok.sum() < 5:
            continue
        w = 1.0 / s[ok] ** 2
        X = sm.add_constant(q[ok])
        try:
            f = sm.WLS(e[ok], X, weights=w).fit()
        except Exception:                                     # noqa: BLE001
            continue
        ic.append(float(f.params[0])); sl.append(float(f.params[1]))
        cr.append(V.zero_crossing(f.params[0], f.params[1]))
    return np.array(sl), np.array(ic), np.array(cr)


# ------------------------------------------------ Amendment 1 item 1 leverage
def flag_amendment1(fit):
    """LOCKED rule: leverage > 2p/n or Cook's D > 4/n, applied mechanically."""
    lev, ck = fit["leverage"], fit["cooks"]
    n = len(lev)
    p = 2
    return (lev > 2 * p / n) | (ck > 4 / n), 2 * p / n, 4 / n
