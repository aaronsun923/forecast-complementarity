"""Estimation helpers for SPEC v1 §5, with the Amendment 1 D.1 fallbacks.

Primary spec: crossed random intercepts
    (1 | forecaster) + (1 | question) + (1 | question:target)
statsmodels has no native crossed-RE syntax; we build it as a single group
with three variance components. If that fit is degenerate, does not converge,
or is intractable, we fall back exactly as SPEC §5 / Amendment 1 D.1 direct:
  - H1: question-clustered OLS WITHOUT forecaster fixed effects
        (GRP is constant within forecaster and would not be identified)
  - H3/H4: question-clustered OLS WITH forecaster fixed effects; GRP is
        absorbed and must be reported as absorbed, not dropped silently.
"""
import time
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf


MIXED_TIME_BUDGET = 900   # seconds per fit; SPEC §8 one-hour tripwire


class FitResult:
    def __init__(self, kind, params, ci, note, extra=None, nobs=None,
                 n_clusters=None, vc=None):
        self.kind = kind            # "mixed" | "ols_cluster"
        self.params = params        # pd.Series
        self.ci = ci                # pd.DataFrame [lo, hi]
        self.note = note
        self.extra = extra or {}
        self.nobs = nobs
        self.n_clusters = n_clusters
        self.vc = vc                # variance components if mixed

    def table(self, keep=None):
        idx = [k for k in self.params.index if keep is None or k in keep]
        return pd.DataFrame({
            "coef": self.params[idx],
            "ci_lo": self.ci.loc[idx, 0],
            "ci_hi": self.ci.loc[idx, 1],
        })


def fit_mixed_crossed(formula, df, want_forecaster=True):
    """Crossed REs via a single group with variance components."""
    d = df.copy()
    d["_g"] = 1
    vc = {"question": "0 + C(question)", "target": "0 + C(target)"}
    if want_forecaster:
        vc["forecaster"] = "0 + C(forecaster)"
    t0 = time.time()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        md = smf.mixedlm(formula, d, groups=d["_g"], re_formula="0", vc_formula=vc)
        res = md.fit(method="lbfgs", maxiter=1000)
    elapsed = time.time() - t0
    ok = bool(getattr(res, "converged", False))
    wmsgs = sorted({str(x.message).strip() for x in caught
                    if "Convergence" in x.category.__name__
                    or "boundary" in str(x.message).lower()})
    vcomp = dict(zip(md.exog_vc.names if hasattr(md, "exog_vc") else vc.keys(),
                     np.atleast_1d(res.vcomp)))
    vcomp["residual"] = float(res.scale)
    note = f"crossed mixed model, converged={ok}, {elapsed:.0f}s"
    if wmsgs:
        note += " — optimiser warnings: " + "; ".join(wmsgs)
    return FitResult(
        "mixed", res.params.drop(labels=[c for c in res.params.index
                                         if c.endswith("Var") or " Var" in c],
                                 errors="ignore"),
        res.conf_int(), note,
        nobs=int(res.nobs), vc=vcomp, extra={"warnings": wmsgs}), ok


def fit_ols_cluster(formula, df, cluster="question", absorb_forecaster=False):
    """Question-clustered OLS; optionally with forecaster fixed effects."""
    f = formula
    if absorb_forecaster:
        f = f + " + C(forecaster)"
    m = smf.ols(f, data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df[cluster]})
    keep = [k for k in m.params.index if not k.startswith("C(forecaster)")]
    note = ("question-clustered OLS with forecaster fixed effects; "
            "GRP absorbed by forecaster fixed effects, not separately reported"
            if absorb_forecaster else
            "question-clustered OLS without forecaster fixed effects "
            "(GRP is constant within forecaster and is not identified with them)")
    return FitResult("ols_cluster", m.params[keep], m.conf_int().loc[keep], note,
                     nobs=int(m.nobs), n_clusters=int(df[cluster].nunique()),
                     extra={"r2": m.rsquared})


def fit_spec(formula, df, hypothesis):
    """Try the SPEC mixed model; fall back per Amendment 1 D.1."""
    try:
        res, ok = fit_mixed_crossed(formula, df)
        if ok and np.all(np.isfinite(res.ci.values)):
            return res, None
        reason = "mixed model did not converge"
    except Exception as e:                                   # noqa: BLE001
        reason = f"mixed model failed: {type(e).__name__}: {e}"
    absorb = hypothesis != "H1"
    fb = fit_ols_cluster(formula, df, absorb_forecaster=absorb)
    fb.note = f"FALLBACK ({reason}). " + fb.note
    return fb, reason


def group_means_cluster(df, value, group_col="GRP", cluster="question"):
    """Group means of `value` with question-clustered 95% CIs (SPEC 5.1)."""
    out = {}
    for g, sub in df.groupby(group_col):
        m = smf.ols(f"{value} ~ 1", data=sub).fit(
            cov_type="cluster", cov_kwds={"groups": sub[cluster]})
        ci = m.conf_int().loc["Intercept"]
        out[g] = dict(mean=float(m.params["Intercept"]),
                      ci_lo=float(ci[0]), ci_hi=float(ci[1]),
                      n=int(len(sub)), n_questions=int(sub[cluster].nunique()),
                      n_forecasters=int(sub["forecaster"].nunique()))
    return pd.DataFrame(out).T


def logit_clip(p, lo, hi):
    q = np.clip(p, lo, hi)
    return np.log(q / (1 - q)), int(np.sum((p < lo) | (p > hi)))


def encompassing(target_df, human_col, clip, cluster="question"):
    """SPEC 5.2: o ~ logit(p_a) + [logit(p_h) - logit(p_a)], clustered SEs."""
    d = target_df.dropna(subset=[human_col, "p_a", "o"]).copy()
    lo, hi = clip
    la, n_a = logit_clip(d["p_a"].values, lo, hi)
    lh, n_h = logit_clip(d[human_col].values, lo, hi)
    X = pd.DataFrame({"logit_p_a": la, "human_minus_model": lh - la}, index=d.index)
    X = sm.add_constant(X)
    m = sm.Logit(d["o"].values, X).fit(
        disp=0, cov_type="cluster",
        cov_kwds={"groups": d[cluster].values, "use_correction": True})
    params = pd.Series(np.asarray(m.params), index=X.columns)
    ci = pd.DataFrame(np.asarray(m.conf_int()), index=X.columns)
    return dict(params=params, ci=ci, nobs=int(len(d)),
                n_clusters=int(d[cluster].nunique()),
                clipped_model=n_a, clipped_human=n_h)
