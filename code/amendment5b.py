"""SPEC v3 Amendment 5b: H2 encompassing test split by question source.

The locked H2 path is not touched. The frame is rebuilt from the fixed raw
snapshot with the same fbdata calls as full.py, and the regression is the v1
function models.encompassing, imported. The target-level table mirrors the
full.py §7 aggregation, with MKT carried along. Before any v3 number, the
pooled v1 H2 result is reproduced and checked against the locked report.

Usage:  python3 code/amendment5b.py
Writes: docs/amendment5b_REPORT.md
"""
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd

import config as CFG
import fbdata as F
import models as M
from report import md_table

warnings.filterwarnings("ignore")

SPEC_COMMIT = "751e0fb68d0d8131044cea92b88375bdf865c499"
LOCKED = {"S": (1.79, 1.04, 2.53), "P": (0.97, 0.24, 1.70)}   # docs/forecast_full_REPORT.md §7
GROUPS = [("S", "p_h_S", "superforecaster median"), ("P", "p_h_P", "public median")]
CLIPS = {"primary": CFG.CLIP, "sensitivity": (0.001, 0.999)}

OUT = []
def w(s=""):
    OUT.append(s)


# ===================================================================== load
rbt, rbq = F.load_resolutions()
humans, dropped, invalid = F.load_humans(rbt, rbq)
models_df, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(models_df, set(humans["target"]))
stats = F.target_level_model_stats(models_df)
full, frame_info = F.build_frame(humans, models_df, stats, chosen)

tl = (full.groupby("target")
      .agg(o=("o", "first"), p_a=("p_a", "first"), question=("question", "first"),
           MKT=("MKT", "first"))
      .reset_index())
tl = (tl.merge(full[full.GRP == "S"].groupby("target")["p_h"].median().rename("p_h_S"),
               on="target", how="left")
        .merge(full[full.GRP == "P"].groupby("target")["p_h"].median().rename("p_h_P"),
               on="target", how="left"))
assert (full.groupby("target")["MKT"].nunique() == 1).all()
assert (tl.groupby("question")["MKT"].nunique() == 1).all(), "a question mixes sources"


def fit(df, clip):
    return {g: M.encompassing(df, col, clip) for g, col, _ in GROUPS}


# ====================================================== reproduction check
pooled = fit(tl, CFG.CLIP)
repro = {}
for g, *_ in GROUPS:
    r = pooled[g]
    got = (r["params"]["human_minus_model"], r["ci"].loc["human_minus_model", 0],
           r["ci"].loc["human_minus_model", 1])
    repro[g] = (got, all(round(x, 2) == y for x, y in zip(got, LOCKED[g])))
if not all(ok for _, ok in repro.values()):
    for g, (got, ok) in repro.items():
        print(g, got, "locked", LOCKED[g], "OK" if ok else "MISMATCH")
    sys.exit("v1 H2 reproduction failed; stopping before any v3 number.")


# ================================================================ split fits
subsets = {"market": tl[tl.MKT == 1], "dataset": tl[tl.MKT == 0]}
res = {(s, c): fit(d, clip) for s, d in subsets.items() for c, clip in CLIPS.items()}


def rows(clip_name):
    out = []
    for s in ["dataset", "market"]:
        for g, col, _ in GROUPS:
            r = res[(s, clip_name)][g]
            ci = r["ci"]
            out.append({
                "source": s, "group": g,
                "coef_human_minus_model": r["params"]["human_minus_model"],
                "ci_lo": ci.loc["human_minus_model", 0],
                "ci_hi": ci.loc["human_minus_model", 1],
                "coef_logit_p_a": r["params"]["logit_p_a"],
                "p_a_ci_lo": ci.loc["logit_p_a", 0],
                "p_a_ci_hi": ci.loc["logit_p_a", 1],
                "n_targets": r["nobs"], "n_questions": r["n_clusters"],
                "clipped_model": r["clipped_model"],
                "clipped_human": r["clipped_human"],
            })
    return pd.DataFrame(out)


prim, sens = rows("primary"), rows("sensitivity")


def cell(df, s, g):
    return df[(df.source == s) & (df.group == g)].iloc[0]


def excl0(r):
    return r.ci_lo > 0 or r.ci_hi < 0


def branch(g):
    d, m = cell(prim, "dataset", g), cell(prim, "market", g)
    d_pos = d.ci_lo > 0
    m_pos = m.ci_lo > 0
    m_has0 = m.ci_lo <= 0 <= m.ci_hi
    d_has0 = d.ci_lo <= 0 <= d.ci_hi
    if d_pos and m_has0:
        return "A", "dataset positive, market interval includes zero: the increment is where the information gap is"
    if d_pos and m_pos:
        return "B", "both positive: the increment is not fully explained by access to newer data points (still not evidence of judgment)"
    if m_pos and d_has0:
        return "C", "market positive, dataset interval includes zero: contrary to the information-gap account"
    return "none", ("no locked branch applies (dataset "
                    f"[{d.ci_lo:.2f}, {d.ci_hi:.2f}], market [{m.ci_lo:.2f}, {m.ci_hi:.2f}])")


br = {g: branch(g) for g, *_ in GROUPS}
nq = tl.groupby("MKT")["question"].nunique()
nt = tl.groupby("MKT")["target"].nunique()
git_head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=CFG.REPO_ROOT).stdout.strip()


def ci2(r, a="ci_lo", b="ci_hi"):
    return f"[{r[a]:.2f}, {r[b]:.2f}]"


# ==================================================================== report
w("# SPEC v3 Amendment 5b: encompassing by question source")
w()
w("Post-results in origin; reading locked in specs/forecast_spec_v3.md "
  f"(commit `{SPEC_COMMIT[:7]}`) before computation. Nothing here changes a v1 or v2 number. "
  "The pooled Section 4.2 (v1 §7) results are unchanged by this amendment.")
w()
w("## Result against the locked reading")
w()
for g, _, label in GROUPS:
    d, m = cell(prim, "dataset", g), cell(prim, "market", g)
    w(f"- **{label.capitalize()}**: dataset {d.coef_human_minus_model:.2f} {ci2(d)}, "
      f"market {m.coef_human_minus_model:.2f} {ci2(m)}. Branch: **{br[g][1]}**.")
w()
w("## Locked reading (restated from SPEC v3)")
w()
w("- Dataset coefficient positive and market interval includes zero: the increment is where the "
  "information gap is. The paper's main claim is restated as \"relative to a model without news, "
  "on questions where humans could retrieve newer data\".")
w("- Both positive: the increment is not fully explained by access to newer data points, since on "
  "market questions both sides shared the freeze price. This is still not evidence of judgment; "
  "the paper says so.")
w("- Market positive and dataset interval includes zero: contrary to the information-gap account. "
  "Reported in the main text as such, not in a footnote.")
w("- The pooled Section 4.2 numbers are not changed by this amendment.")
w()
w("## Estimates")
w()
w("Target level, logistic, `o ~ logit(p_a) + [logit(p_h) - logit(p_a)]`, question-clustered SEs, "
  "benchmark (a) unchanged (`" + str(chosen) + "`), groups fit separately. "
  "Function: `models.encompassing` (v1), imported.")
w()
w(f"Sources: **{int(nt[0])} dataset targets on {int(nq[0])} questions; "
  f"{int(nt[1])} market targets on {int(nq[1])} questions.** No question mixes sources.")
w()
fmt = lambda df: (df.assign(**{k: df[k].map(lambda x: f"{x:.2f}") for k in
                               ["coef_human_minus_model", "ci_lo", "ci_hi",
                                "coef_logit_p_a", "p_a_ci_lo", "p_a_ci_hi"]})
                  .set_index(["source", "group"]))
w(f"**Primary, clip {CFG.CLIP}:**")
w()
w(md_table(fmt(prim)))
w()
w("**Sensitivity, clip (0.001, 0.999):**")
w()
w(md_table(fmt(sens)))
w()
w(f"`clipped_model` / `clipped_human` count targets where benchmark (a) / the human median falls "
  f"outside the clip bounds. The market subset has only {int(nt[1])} targets across "
  f"{int(nq[1])} market questions (one target per question, so clustering is nominal there); "
  f"its intervals are correspondingly wide.")
w()
w("## Checklist")
w()
w(f"- Spec commit: `{SPEC_COMMIT}` (specs/forecast_spec_v3.md, committed before any v3 "
  f"computation; not pushed). Repo HEAD at run: `{git_head}`.")
w("- Locked reading: restated above.")
for g, _, label in GROUPS:
    w(f"- Branch, {label}: {br[g][0]} — {br[g][1]}.")
w("- Reproduction check (untouched v1 H2 path, pooled, clip (0.01, 0.99)): "
  + "; ".join(f"{g} {got[0]:.2f} [{got[1]:.2f}, {got[2]:.2f}] vs locked "
              f"{LOCKED[g][0]:.2f} [{LOCKED[g][1]:.2f}, {LOCKED[g][2]:.2f}] — "
              f"{'match' if ok else 'MISMATCH'}"
              for g, (got, ok) in repro.items()) + ".")
w()

(CFG.DOCS / "amendment5b_REPORT.md").write_text("\n".join(OUT))
print("\n".join(OUT))
