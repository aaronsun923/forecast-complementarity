"""Reviewer 2, Task B: which variance component sits at the boundary.

No fit object was stored by full.py, pilot.py or v2_full.py, so every mixed
model reported under SPEC v1 and SPEC v2 is refitted here through the same code
path (models.fit_mixed_crossed, then the fit_spec fallback rule) on the same
frames. A fit's variance components are accepted only if the refit reproduces
the published fixed effects: v1 fits must reproduce every row of their printed
table (%.5f) in the report; v2 eps fits must reproduce the eps point estimate,
its CI, and the boundary-warning and fallback flags stored in
data/derived/v2_full_A_stage1.pkl. Nothing is re-estimated in any other way.

Boundary rule: a random component (forecaster, question, target within question)
is "at boundary" if its estimated variance is below 1e-6 or below 0.1% of the
residual variance.

Usage:  python3 code/boundary_components.py
Writes: docs/boundary_components.csv, and appends (or replaces) the section
        "Boundary components (variance at zero)" in docs/forecast_full_REPORT.md.
"""
import os
import pickle
import re
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

import config as CFG
import fbdata as F
import models as M
from report import md_table

warnings.filterwarnings("ignore")

HEADING = "## Boundary components (variance at zero)"
ABS_TOL, REL_TOL = 1e-6, 1e-3
RE = ["forecaster", "question", "target"]
ZCOLS = ["DIS", "CONF_a", "logHZ", "EXT_a", "absD_a",
         "DIS_all34", "EXT_b", "absD_b", "CONF_b"]
F3 = "G_a ~ DIS_z + CONF_a_z + logHZ_z + MKT + GRP"
F4 = ("G_a ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + MKT + GRP "
      "+ EXT_a_z:DIS_z")
F3b = "G_b ~ DIS_z + CONF_b_z + logHZ_z + MKT + GRP"
F4b = ("G_b ~ EXT_b_z + absD_b_z + DIS_z + CONF_b_z + logHZ_z + MKT + GRP "
       "+ EXT_b_z:DIS_z")
F3l = "G_log ~ DIS_z + CONF_a_z + logHZ_z + MKT + GRP"
F4l = ("G_log ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + MKT + GRP "
       "+ EXT_a_z:DIS_z")
F3d = "G_a ~ DIS_z + CONF_a_z + logHZ_z + GRP"
F4d = ("G_a ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + logHZ_z + GRP "
       "+ EXT_a_z:DIS_z")

# (fit_id, family, report, formula, hypothesis, frame key)
V1_JOBS = [
    ("v1_full_H1", "v1 H1", "full", "G_a ~ GRP", "H1", "full"),
    ("v1_full_H3_primary", "v1 H3", "full", F3, "H3", "full"),
    ("v1_full_H3_DIS_all34", "v1 H3", "full", F3.replace("DIS_z", "DIS_all34_z"), "H3", "full"),
    ("v1_full_H3_baseline_b", "v1 H3", "full", F3b, "H3", "full"),
    ("v1_full_H3_log", "v1 H3", "full", F3l, "H3", "full"),
    ("v1_full_H3_dataset_only", "v1 H3", "full", F3d, "H3", "full_ds"),
    ("v1_full_H4_primary", "v1 H4", "full", F4, "H4", "full"),
    ("v1_full_H4_noncrossing", "v1 H4", "full", F4, "H4", "full_nc"),
    ("v1_full_H4_baseline_b", "v1 H4", "full", F4b, "H4", "full"),
    ("v1_full_H4_log", "v1 H4", "full", F4l, "H4", "full"),
    ("v1_full_H4_dataset_only", "v1 H4", "full", F4d, "H4", "full_ds"),
    ("v1_pilot_H1", "v1 pilot", "pilot", "G_a ~ GRP", "H1", "pilot"),
    ("v1_pilot_H3_primary", "v1 pilot", "pilot", F3, "H3", "pilot"),
    ("v1_pilot_H3_DIS_all34", "v1 pilot", "pilot", F3.replace("DIS_z", "DIS_all34_z"), "H3", "pilot"),
    ("v1_pilot_H4_primary", "v1 pilot", "pilot", F4, "H4", "pilot"),
    ("v1_pilot_H3_baseline_b", "v1 pilot", "pilot", F3b, "H3", "pilot"),
    ("v1_pilot_H4_baseline_b", "v1 pilot", "pilot", F4b, "H4", "pilot"),
    ("v1_pilot_H3_log", "v1 pilot", "pilot", F3l, "H3", "pilot"),
    ("v1_pilot_H4_log", "v1 pilot", "pilot", F4l, "H4", "pilot"),
    ("v1_pilot_H3_dataset_only", "v1 pilot", "pilot", F3d, "H3", "pilot_ds"),
    ("v1_pilot_H4_dataset_only", "v1 pilot", "pilot", F4d, "H4", "pilot_ds"),
    ("v1_pilotnote_H3", "v1 pilot", "full_note", F3, "H3", "full_pil"),
    ("v1_pilotnote_H4", "v1 pilot", "full_note", F4, "H4", "full_pil"),
]
V2_STAGE1 = CFG.DERIVED / "v2_full_A_stage1.pkl"


# ------------------------------------------------------------ worker state
_S = {}


def _zs(d):
    for c in ZCOLS:
        d[c + "_z"] = F.zscore(d[c])
    return d


def v1_frame(key):
    if key in _S:
        return _S[key]
    if key.startswith("full"):
        full = pd.read_pickle(CFG.DERIVED / "full_frame.pkl")
        if key == "full":
            d = full
        elif key == "full_nc":
            d = _zs(full[~full.crossing].copy())
        elif key == "full_ds":
            d = _zs(full[full.MKT == 0].copy())
        else:   # full.py reporting note: pilot questions of the full frame
            pq, _ = F.pilot_questions(full["question"].unique())
            d = _zs(full[full["question"].isin(pq)].copy())
    else:
        pil = pd.read_parquet(CFG.DERIVED / "pilot_frame.parquet")
        d = pil if key == "pilot" else _zs(pil[pil.MKT == 0].copy())
    _S[key] = d
    return d


def v2_frame(model):
    import v2full as W
    if "v2" not in _S:
        rbt, rbq = F.load_resolutions()
        hum, _, _ = F.load_humans(rbt, rbq)
        mods, _ = F.load_matched_models()
        _S["v2"] = (hum, mods, F.target_level_model_stats(mods))
    hum, mods, stats = _S["v2"]
    if ("v2f", model) not in _S:
        _S[("v2f", model)] = F.build_frame(hum, mods, stats, model)[0]
    return _S[("v2f", model)], W.prep_group


def fit(formula, df, hypothesis):
    """models.fit_spec, keeping the mixed attempt's variance components."""
    vc, warn, conv, err = {}, False, False, None
    try:
        res, ok = M.fit_mixed_crossed(formula, df)
        vc, warn, conv = res.vc, bool(res.extra.get("warnings")), ok
        if ok and np.all(np.isfinite(res.ci.values)):
            return res, vc, warn, conv, None
        reason = "mixed model did not converge"
    except Exception as e:                                   # noqa: BLE001
        reason = f"mixed model failed: {type(e).__name__}: {e}"
    fb = M.fit_ols_cluster(formula, df, absorb_forecaster=hypothesis != "H1")
    return fb, vc, warn, conv, reason


# ----------------------------------------------------------------- jobs
def run_v1(job, report_text):
    fid, fam, rep, formula, hyp, key = job
    df = v1_frame(key)
    res, vc, warn, conv, fb = fit(formula, df, hyp)
    tbl = res.table()
    if rep == "full_note":
        # full.py reporting-note table: pilot column only, %.5f
        want = {"H3": [("H3 DIS_z", "DIS_z")],
                "H4": [("H4 EXT_a_z", "EXT_a_z"), ("H4 EXT_a_z:DIS_z", "EXT_a_z:DIS_z")]}[hyp]
        lines = [f"| {lab} | {tbl.loc[p, 'coef']:.5f} |" for lab, p in want]
    else:
        lines = md_table(tbl, floatfmt="%.5f").splitlines()[2:]
    missing = [ln for ln in lines if ln not in report_text]
    return dict(fit_id=fid, family=fam, spec="v1", formula=formula, frame=key,
                nobs=res.nobs, n_coef_rows_checked=len(lines),
                check_passed=not missing,
                check_detail="all printed rows reproduced" if not missing
                else "not reproduced: " + " / ".join(missing[:3]),
                **_common(res, vc, warn, conv, fb))


def run_v2(model, grp, y, stored):
    fr, prep = v2_frame(model)
    sub = prep(fr[fr.GRP == grp])
    import v2common as V
    res, vc, warn, conv, fb = fit(V.F4_GROUP.replace("G_a", y), sub, "H4")
    tag = "" if y == "G_a" else "_log"
    c = f"eps{tag}_{grp}"
    got = (float(res.params["EXT_a_z"]), float(res.ci.loc["EXT_a_z", 0]),
           float(res.ci.loc["EXT_a_z", 1]))
    ref = (stored[c], stored[c + "_lo"], stored[c + "_hi"])
    dmax = max(abs(a - b) for a, b in zip(got, ref))
    fb_ok = (fb is None) == bool(pd.isna(stored[c + "_fb"]))
    warn_ok = (warn == bool(stored[c + "_warn"])) if fb is None else True
    ok = round(got[0], 4) == round(ref[0], 4) and dmax < 5e-5 and fb_ok and warn_ok
    fam = "v2 eps (Brier)" if y == "G_a" else "v2 eps (log)"
    return dict(fit_id=f"v2_eps{tag}_{grp}|{model}", family=fam, spec="v2",
                formula=V.F4_GROUP.replace("G_a", y), frame=f"{model}, group {grp}",
                nobs=res.nobs, n_coef_rows_checked=1, check_passed=bool(ok),
                check_detail=(f"eps, CI max |diff| vs stored {dmax:.1e}; "
                              f"fallback flag {'matches' if fb_ok else 'DIFFERS'}; "
                              f"warning flag {'matches' if warn_ok else 'DIFFERS'}"),
                **_common(res, vc, warn, conv, fb))


def _common(res, vc, warn, conv, fb):
    out = dict(reported_estimator="mixed" if fb is None else "OLS fallback",
               mixed_converged=conv, boundary_warning=warn,
               fallback_reason=fb or "")
    resid = vc.get("residual", np.nan)
    out["var_residual"] = resid
    for k in RE:
        v = vc.get(k, np.nan)
        out[f"var_{k}"] = v
        out[f"at_boundary_{k}"] = (bool(v < ABS_TOL or v < REL_TOL * resid)
                                   if np.isfinite(v) else None)
    return out


def _task(kind, args):
    t = time.time()
    r = run_v1(*args) if kind == "v1" else run_v2(*args)
    r["_secs"] = round(time.time() - t, 1)
    return r


# ----------------------------------------------------------------- main
def main():
    texts = {"full": (CFG.DOCS / "forecast_full_REPORT.md").read_text(),
             "pilot": (CFG.DOCS / "forecast_pilot_REPORT.md").read_text()}
    texts["full_note"] = texts["full"]
    s1 = pickle.loads(V2_STAGE1.read_bytes())["s1"]

    tasks = [("v1", (j, texts[j[2]])) for j in V1_JOBS]
    for model in s1.index:
        stored = s1.loc[model].to_dict()
        for grp in ("S", "P"):
            for y in ("G_a", "G_log"):
                tasks.append(("v2", (model, grp, y, stored)))
    print(f"{len(tasks)} fits", flush=True)

    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=int(os.environ.get("BC_WORKERS", "8"))) as ex:
        futs = [ex.submit(_task, k, a) for k, a in tasks]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            rows.append(r)
            print(f"[{i:3d}/{len(tasks)}] {time.time()-t0:6.0f}s {r['fit_id'][:70]:70s} "
                  f"check={'ok' if r['check_passed'] else 'FAIL'}", flush=True)

    order = [j[0] for j in V1_JOBS]
    df = pd.DataFrame(rows)
    df["_o"] = df["fit_id"].map(lambda x: order.index(x) if x in order else 10**6)
    df = df.sort_values(["_o", "family", "fit_id"]).drop(columns=["_o", "_secs"])
    cols = (["fit_id", "family", "spec", "frame", "formula", "nobs", "reported_estimator",
             "mixed_converged", "boundary_warning"]
            + [f"var_{k}" for k in RE] + ["var_residual"]
            + [f"at_boundary_{k}" for k in RE]
            + ["check_passed", "check_detail", "fallback_reason"])
    df = df[cols]
    df.to_csv(CFG.DOCS / "boundary_components.csv", index=False, float_format="%.6g")

    # ---- summary per family (mixed-reported fits only for the counts)
    fams = ["v1 H1", "v1 H3", "v1 H4", "v1 pilot", "v2 eps (Brier)", "v2 eps (log)"]
    srows = []
    for fam in fams:
        d = df[df.family == fam]
        m = d[d.reported_estimator == "mixed"]
        srows.append({"family": fam, "fits": len(d),
                      "reported as mixed": len(m),
                      "OLS fallback": int((d.reported_estimator != "mixed").sum()),
                      "boundary warning": int(m.boundary_warning.sum()),
                      **{f"{k} at boundary": int(m[f"at_boundary_{k}"].astype(bool).sum())
                         for k in RE},
                      "no component at boundary": int((~m[[f"at_boundary_{k}" for k in RE]]
                                                       .astype(bool).any(axis=1)).sum())})
    summ = pd.DataFrame(srows).set_index("family")
    summ.loc["total"] = summ.sum()

    fbd = df[df.reported_estimator != "mixed"]
    fb_note = (f"{len(fbd)} fits were reported as the question-clustered OLS fallback "
               "(the mixed attempt did not converge). They carry no reported variance "
               "components and are left out of the component counts; the CSV still lists "
               "what their non-converged mixed attempt estimated, for reference. "
               f"Of those attempts, {int(fbd[[f'at_boundary_{k}' for k in RE]].fillna(False).astype(bool).any(axis=1).sum())} "
               "had a component at the boundary.") if len(fbd) else \
        "No fit fell back to OLS."
    L = [HEADING, "",
         "Added for the second review. For every mixed model reported under SPEC v1 (full "
         "run: H1, H3 primary and sensitivities, H4 primary and sensitivities; the pilot "
         "fits, including the two pilot refits in the reporting note) and SPEC v2 (the 136 "
         "eps fits: 34 variants, two groups, Brier and log score), the estimated variance "
         "of each random intercept and of the residual.", "",
         "No fit object was stored, so each model was refitted with the stored code "
         "(`models.fit_mixed_crossed` and the `fit_spec` fallback rule) on the same frame. "
         "A refit counts only if it reproduces the published fixed effects: every printed "
         "coefficient row (%.5f) for v1, and the eps estimate, its CI, and the stored "
         "warning and fallback flags for v2. "
         f"**{int(df.check_passed.sum())} of {len(df)} refits pass that check.**", "",
         f"**Rule.** A random component is at the boundary if its estimated variance is "
         f"below {ABS_TOL:g} or below {100*REL_TOL:g}% of the residual variance.", "",
         md_table(summ, floatfmt="%.0f"), "",
         fb_note, "",
         "Per-fit values: `docs/boundary_components.csv`.", ""]
    if not df.check_passed.all():
        bad = df[~df.check_passed]
        L += ["Refits that did not reproduce the published estimate:", "",
              md_table(bad[["fit_id", "check_detail"]].set_index("fit_id")), ""]
    section = "\n".join(L)
    rp = CFG.DOCS / "forecast_full_REPORT.md"
    text = rp.read_text()
    if HEADING in text:
        text = re.sub(re.escape(HEADING) + r".*?(?=\n## |\Z)", section.rstrip("\n") + "\n",
                      text, flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n---\n\n" + section
    rp.write_text(text)
    print(summ.to_string())
    print(df.groupby("family")[["var_forecaster", "var_question", "var_target",
                                "var_residual"]].median().to_string())


if __name__ == "__main__":
    sys.exit(main())
