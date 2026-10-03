"""SPEC v3 Amendment 5: news-augmented variants.

The locked v1 path is not touched. News variants are loaded with the v1 loader
(fbdata.load_matched_models) by temporarily widening config.MATCHED_SCAFFOLDS
to the news scaffolds; the regression is models.encompassing (v1 H2); the
paired bootstrap uses v2common.fast_logit, validated against
models.encompassing on the full sample at run time.

Usage:  python3 code/amendment5.py
Writes: docs/amendment5_REPORT.md, or docs/amendment5_coverage.md if no news
        variant passes the coverage gate.
"""
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd

import config as CFG
import fbdata as F
import models as M
import v2common as V
from report import md_table

warnings.filterwarnings("ignore")

SPEC_COMMIT = "751e0fb68d0d8131044cea92b88375bdf865c499"
LOCKED = {"S": (1.79, 1.04, 2.53), "P": (0.97, 0.24, 1.70)}   # docs/forecast_full_REPORT.md §7
GROUPS = [("S", "p_h_S", "superforecaster median"), ("P", "p_h_P", "public median")]
SONNET = "Claude-3-5-Sonnet-20240620"
SPEC_LISTED = ["scratchpad with news", "scratchpad with news with freeze values"]
COVERAGE_MIN = 0.90
DRAWS = 2000
SEED = 20260906

OUT = []
def w(s=""):
    OUT.append(s)


# ============================================================ v1 frame + check
rbt, rbq = F.load_resolutions()
humans, dropped, invalid = F.load_humans(rbt, rbq)
models_df, meta = F.load_matched_models()
rank, chosen, sel_targets = F.select_baseline_a(models_df, set(humans["target"]))
stats = F.target_level_model_stats(models_df)
full, _ = F.build_frame(humans, models_df, stats, chosen)
tl = V.target_level(full)
test_targets = set(tl["target"])
assert len(tl) == 578

repro = {}
for g, col, _ in GROUPS:
    r = M.encompassing(tl, col, CFG.CLIP)
    got = (r["params"]["human_minus_model"], r["ci"].loc["human_minus_model", 0],
           r["ci"].loc["human_minus_model", 1])
    repro[g] = (got, all(round(x, 2) == y for x, y in zip(got, LOCKED[g])))
if not all(ok for _, ok in repro.values()):
    sys.exit(f"v1 H2 reproduction failed: {repro}; stopping before any v3 number.")
Q_a = float(rank.loc[chosen, "brier"])


# ============================================================ news variants
news_scaffolds = None
_saved = CFG.MATCHED_SCAFFOLDS
try:
    import json
    sc = set()
    for p in sorted(CFG.MODEL_DIR.glob("*.json")):
        s = F.parse_model(json.loads(p.read_text())["model"])[1]
        if s and "news" in s.lower():
            sc.add(s)
    news_scaffolds = tuple(sorted(sc))
    CFG.MATCHED_SCAFFOLDS = news_scaffolds
    news_df, news_meta = F.load_matched_models()
finally:
    CFG.MATCHED_SCAFFOLDS = _saved

# selection-set Brier Q on the v1 selection set (single targets no human forecast)
n_sel = len(sel_targets)
sel = news_df[news_df["resolved"] & news_df["target"].isin(sel_targets)].copy()
sel["bs"] = (sel["p"] - sel["resolved_to"]) ** 2
ok_sel = sel[~sel["imputed"]]
vt = pd.DataFrame({
    "Q_sel": ok_sel.groupby("model")["bs"].mean(),
    "n_sel_scored": ok_sel.groupby("model").size(),
    "sel_imputed_share": sel.groupby("model")["imputed"].sum() / n_sel,
}).join(news_meta.set_index("model")[["base", "scaffold"]], how="right")
vt["n_sel_scored"] = vt["n_sel_scored"].fillna(0).astype(int)
vt["sel_eligible"] = vt["sel_imputed_share"] <= CFG.IMPUTED_ELIGIBILITY_MAX

test = news_df[news_df["target"].isin(test_targets)]
vt["test_targets_nonimputed"] = (test[~test["imputed"]].groupby("model")["target"]
                                 .nunique()).reindex(vt.index).fillna(0).astype(int)
vt["test_imputed"] = test.groupby("model")["imputed"].sum().reindex(vt.index).fillna(0).astype(int)
vt["coverage"] = vt["test_targets_nonimputed"] / len(test_targets)
vt["test_imputed_share"] = vt["test_imputed"] / len(test_targets)

# objects
sonnet_listed = [f"{SONNET} ({s})" for s in SPEC_LISTED]
sonnet_other = [m for m in vt.index if vt.loc[m, "base"] == SONNET
                and vt.loc[m, "scaffold"].startswith("scratchpad")
                and m not in sonnet_listed]
best_any = vt[vt["sel_eligible"]].sort_values("Q_sel").index[0]
objects = {}
for m in sonnet_listed:
    objects[m] = "Sonnet scratchpad with news (spec-listed)"
for m in sonnet_other:
    objects[m] = "Sonnet scratchpad with news (not in spec parenthetical; flagged)"
objects[best_any] = (objects.get(best_any, "") + "; " if best_any in objects else "") + \
    "best selection-set Q among news variants of any base model"
for m in objects:
    assert m in vt.index, m

obj = vt.loc[list(objects)].copy()
obj["role"] = [objects[m] for m in obj.index]
obj["gate_coverage"] = obj["coverage"] >= COVERAGE_MIN
obj["gate_imputed"] = obj["sel_imputed_share"] <= CFG.IMPUTED_ELIGIBILITY_MAX
obj["passes"] = obj["gate_coverage"] & obj["gate_imputed"]

git_head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=CFG.REPO_ROOT).stdout.strip()
repro_line = ("Reproduction check (untouched v1 H2 path, pooled, clip (0.01, 0.99)): "
              + "; ".join(f"{g} {got[0]:.2f} [{got[1]:.2f}, {got[2]:.2f}] vs locked "
                          f"{LOCKED[g][0]:.2f} [{LOCKED[g][1]:.2f}, {LOCKED[g][2]:.2f}] — "
                          f"{'match' if ok else 'MISMATCH'}" for g, (got, ok) in repro.items())
              + ".")

LOCKED_READING = [
    "If the news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot "
    "narrow the information-set confound. The paper reports only that the ForecastBench news "
    "pipeline did not improve this model in this round, and does not read a positive human "
    "coefficient against the news variant as evidence of judgment.",
    "If the news variant's Q is not worse, and the public median's coefficient against the best "
    "news variant has an interval including zero: the public increment over the freeze-only model "
    "is consistent with retrievable news. The main claim is restated as \"relative to a single "
    "model without news\".",
    "If the news variant's Q is not worse, and the public coefficient stays positive: the "
    "increment is not absorbed by this news pipeline. The paper adds in the same sentence that "
    "the pipeline may retrieve less than a human does, so this is still not evidence of judgment.",
    "The superforecaster coefficient is reported but never used as identification evidence on its "
    "own, because of the group stage.",
    "No v1 number changes. The primary benchmark is not reselected.",
]

gate_cols = ["role", "Q_sel", "n_sel_scored", "sel_imputed_share", "coverage",
             "test_targets_nonimputed", "test_imputed", "passes"]


def gate_table(df):
    d = df[gate_cols].copy()
    d["Q_sel"] = d["Q_sel"].map(lambda x: f"{x:.4f}")
    d["sel_imputed_share"] = d["sel_imputed_share"].map(lambda x: f"{100*x:.1f}%")
    d["coverage"] = d["coverage"].map(lambda x: f"{100*x:.1f}%")
    return md_table(d)


if not obj["passes"].any():
    w("# SPEC v3 Amendment 5: coverage gate")
    w()
    w("No news variant passes the coverage gate; Amendment 5 stops here.")
    w()
    w(gate_table(obj))
    w()
    w(f"- Spec commit: `{SPEC_COMMIT}`. Repo HEAD at run: `{git_head}`.")
    w(f"- {repro_line}")
    (CFG.DOCS / "amendment5_coverage.md").write_text("\n".join(OUT))
    print("\n".join(OUT))
    sys.exit(0)


# ============================================================ encompassing
passing = list(obj.index[obj["passes"]])
p_news = (news_df[~news_df["imputed"] & news_df["target"].isin(test_targets)]
          .set_index(["model", "target"])["p"])


def common_tl(m):
    d = tl.copy()
    d["p_news"] = d["target"].map(p_news.xs(m, level="model"))
    return d[d["p_news"].notna() & d["p_a"].notna()].reset_index(drop=True)


def fit_row(d, model_col, col):
    dd = d.copy()
    dd["p_a"] = dd[model_col]
    r = M.encompassing(dd, col, CFG.CLIP)
    return r


def boot_diff(d, col):
    """Question-level cluster bootstrap of beta(news) - beta(a), same draws for both."""
    rng = np.random.default_rng(SEED)
    qs = d["question"].unique()
    idx = {q: np.flatnonzero(d["question"].values == q) for q in qs}
    y = d["o"].values.astype(float)
    lh = V.logit_clip(d[col].values)
    ln = V.logit_clip(d["p_news"].values)
    la = V.logit_clip(d["p_a"].values)
    out, fails = [], 0
    for _ in range(DRAWS):
        pick = rng.choice(qs, size=len(qs), replace=True)
        rows = np.concatenate([idx[q] for q in pick])
        clus = np.concatenate([np.full(len(idx[q]), j) for j, q in enumerate(pick)])
        bb = []
        for lm in (ln, la):
            X = np.column_stack([np.ones(len(rows)), lm[rows], lh[rows] - lm[rows]])
            b, _ = V.fast_logit(X, y[rows], clus)
            bb.append(None if b is None else b[2])
        if None in bb:
            fails += 1
            continue
        out.append(bb[0] - bb[1])
    return np.array(out), fails


results, max_dev = [], 0.0
for m in passing:
    d = common_tl(m)
    for g, col, label in GROUPS:
        rn = fit_row(d, "p_news", col)
        ra = fit_row(d, "p_a", col)
        # validate fast_logit against the v1 function on the full common sample
        for r, mc in ((rn, "p_news"), (ra, "p_a")):
            lm = V.logit_clip(d[mc].values)
            X = np.column_stack([np.ones(len(d)), lm, V.logit_clip(d[col].values) - lm])
            b, _ = V.fast_logit(X, d["o"].values.astype(float),
                                pd.factorize(d["question"])[0])
            max_dev = max(max_dev, abs(b[2] - r["params"]["human_minus_model"]))
        diffs, fails = boot_diff(d, col)
        lo, hi = V.pct_ci(diffs)
        results.append(dict(
            model=m, group=g,
            beta_news=rn["params"]["human_minus_model"],
            news_lo=rn["ci"].loc["human_minus_model", 0],
            news_hi=rn["ci"].loc["human_minus_model", 1],
            coef_logit_news=rn["params"]["logit_p_a"],
            beta_a_same=ra["params"]["human_minus_model"],
            a_lo=ra["ci"].loc["human_minus_model", 0],
            a_hi=ra["ci"].loc["human_minus_model", 1],
            diff=rn["params"]["human_minus_model"] - ra["params"]["human_minus_model"],
            diff_lo=lo, diff_hi=hi, boot_used=len(diffs), boot_fail=fails,
            n_targets=rn["nobs"], n_questions=rn["n_clusters"],
            clipped_news=rn["clipped_model"], clipped_a=ra["clipped_model"],
            clipped_human=rn["clipped_human"]))
res = pd.DataFrame(results)


# ============================================================ reading
def branch(m):
    if obj.loc[m, "Q_sel"] > Q_a:
        return "1", ("news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 "
                     "cannot narrow the information-set confound")
    r = res[(res.model == m) & (res.group == "P")].iloc[0]
    if r.news_lo <= 0 <= r.news_hi:
        return "2", ("Q not worse and public interval includes zero: public increment consistent "
                     "with retrievable news")
    if r.news_lo > 0:
        return "3", ("Q not worse and public coefficient positive: increment not absorbed by this "
                     "news pipeline (still not evidence of judgment)")
    return "none", "Q not worse and public coefficient negative with interval excluding zero; no locked branch"


best_pass = obj.loc[passing].sort_values("Q_sel").index[0]
br = {m: branch(m) for m in passing}


def short(m):
    return m.replace(f"{SONNET} ", "Sonnet 3.5 ")


# ============================================================ report
w("# SPEC v3 Amendment 5: news-augmented variants")
w()
w("Post-results in origin; reading locked in specs/forecast_spec_v3.md "
  f"(commit `{SPEC_COMMIT[:7]}`) before computation. No v1 number changes; the primary "
  "benchmark is not reselected.")
w()
w("## Result against the locked reading")
w()
w(f"Benchmark (a), `{chosen}`, has selection-set Q = {Q_a:.4f}. "
  f"Best news variant passing the gate by selection-set Q: `{best_pass}` "
  f"(Q = {obj.loc[best_pass, 'Q_sel']:.4f}). **Branch {br[best_pass][0]}: {br[best_pass][1]}.**")
w()
for m in passing:
    if m != best_pass:
        w(f"- `{short(m)}` (Q = {obj.loc[m, 'Q_sel']:.4f}): branch {br[m][0]}, {br[m][1]}.")
w()
w("## Locked reading (restated from SPEC v3)")
w()
for s in LOCKED_READING:
    w(f"- {s}")
w()
w("## Objects and coverage gate")
w()
w(f"News scaffolds in the round: {', '.join(news_scaffolds)}. "
  f"Selection set: the v1 selection set ({n_sel} single targets no human forecast), "
  f"Brier on non-imputed rows, as in v1 §4. Coverage: share of the {len(test_targets)} test "
  f"targets with a non-imputed forecast; gate ≥ {COVERAGE_MIN:.0%}. Imputed rule: v1 A.3 "
  f"selection-set imputed share ≤ {CFG.IMPUTED_ELIGIBILITY_MAX:.0%}.")
w()
w(gate_table(obj))
w()
w(f"Benchmark (a) for comparison: Q = {Q_a:.4f}, selection-set imputed share "
  f"{100*rank.loc[chosen, 'imputed_share']:.1f}%.")
w()
w("**Interpretation flag.** The spec names \"every claude-3-5-sonnet-20240620 scratchpad variant "
  "that carries news (with news; with news and freeze values)\". The round also contains "
  f"`{', '.join(sonnet_other) or 'none'}`, a Sonnet scratchpad variant that carries news but is "
  "not in the parenthetical. It is run and shown but labelled; it does not enter the branch "
  "statement unless it is the best passing variant by Q.")
w()
w("**What \"superforecaster with news 1\" is.** In the ForecastBench code "
  "(forecastbench-code, `src/helpers/llm_crowd_prompts.py` at the parent of commit 6566923, "
  "`SUPERFORECASTER_*_PROMPT_1`) it is a 15-step structured prompt (\"You are an expert "
  "superforecaster\" framing; base rate, reasons up and down, odds, conditional statements, "
  "final probability) filled with the question, background, resolution criteria, dates, and "
  "`retrieved_info` (titles and summaries of retrieved news articles); the dataset version also "
  "carries the latest data value at freeze, and the current `forecast_variants.py` declares "
  "`market_prompt_uses_freeze_values=False` for this variant, so on market questions it did not "
  "see the market freeze value that benchmark (a) saw. The template has no field for any "
  "ForecastBench human (superforecaster or public) forecast. Not verified: the code that "
  "actually ran this variant in the 2024-07-21 round is not in the local snapshot, so the "
  "template-to-variant mapping rests on the names and the variant declaration, not on the run "
  "code.")
w()
w("Selection-set Q for every news variant (all base models), for reference:")
w()
allq = vt.sort_values("Q_sel")[["Q_sel", "n_sel_scored", "sel_imputed_share", "coverage"]].copy()
allq["Q_sel"] = allq["Q_sel"].map(lambda x: f"{x:.4f}")
allq["sel_imputed_share"] = allq["sel_imputed_share"].map(lambda x: f"{100*x:.1f}%")
allq["coverage"] = allq["coverage"].map(lambda x: f"{100*x:.1f}%")
w(md_table(allq))
w()
w("## Encompassing fits")
w()
w(f"`o ~ logit(p_m) + [logit(p_h) - logit(p_m)]`, `models.encompassing` (v1), clip {CFG.CLIP}, "
  "question-clustered SEs, on targets covered (non-imputed) by both the news variant and "
  "benchmark (a). `beta_a_same` is benchmark (a) refit on the same targets. `diff` = beta_news "
  f"- beta_a_same with a question-level cluster bootstrap percentile interval ({DRAWS} draws, "
  f"seed {SEED}; both coefficients refit on the same draw).")
w()
tab = res.copy()
tab["model"] = tab["model"].map(short)
for c in ["beta_news", "news_lo", "news_hi", "coef_logit_news", "beta_a_same", "a_lo", "a_hi",
          "diff", "diff_lo", "diff_hi"]:
    tab[c] = tab[c].map(lambda x: f"{x:.2f}")
tab["beta_news"] = tab["beta_news"] + " [" + tab["news_lo"] + ", " + tab["news_hi"] + "]"
tab["beta_a_same"] = tab["beta_a_same"] + " [" + tab["a_lo"] + ", " + tab["a_hi"] + "]"
tab["diff"] = tab["diff"] + " [" + tab["diff_lo"] + ", " + tab["diff_hi"] + "]"
w(md_table(tab[["model", "group", "beta_news", "coef_logit_news", "beta_a_same", "diff",
                "n_targets", "n_questions", "clipped_news", "clipped_a", "clipped_human",
                "boot_fail"]].set_index(["model", "group"])))
w()
w(f"fast_logit vs models.encompassing on the full common samples: max |Δ human coefficient| = "
  f"{max_dev:.2e}.")
w()
w("The superforecaster rows are reported but are not identification evidence on their own "
  "(group stage).")
w()
w("## Checklist")
w()
w(f"- Spec commit: `{SPEC_COMMIT}`. Repo HEAD at run: `{git_head}`. Amendment 5 results not committed.")
w("- Locked reading: restated above.")
w(f"- Branch (best passing news variant, `{short(best_pass)}`): {br[best_pass][0]} — {br[best_pass][1]}.")
w(f"- {repro_line}")
w()

(CFG.DOCS / "amendment5_REPORT.md").write_text("\n".join(OUT))
print("\n".join(OUT))
