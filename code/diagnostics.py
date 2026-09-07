"""Amendment 3 post-hoc diagnostic for the H4 Brier/log-score sign reversal.

Diagnostic only. Reads the analysis frame saved by full.py and refits NOTHING;
no pre-registered estimate is touched. Inserts a "Post-hoc diagnostics
(not pre-registered)" section into docs/forecast_full_REPORT.md, immediately
before the closing "## Stop" section, and writes one figure.

Idempotent: re-running replaces the section rather than appending a second one.

Usage:  python3 code/diagnostics.py
"""
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as CFG
from report import md_table

MARKER_START = "<!-- posthoc:start -->"
MARKER_END = "<!-- posthoc:end -->"

d = pd.read_pickle(CFG.DERIVED / "full_frame.pkl")

# --- quartiles of EXT_a on the primary analysis rows -------------------
d = d.copy()
d["EXT_q"] = pd.qcut(d["EXT_a"], 4, labels=["Q1", "Q2", "Q3", "Q4"])
edges = np.quantile(d["EXT_a"], [0, .25, .5, .75, 1])

# --- confidently-wrong indicators (Amendment 3 items 2 and 3) ----------
d["wrong_h"] = ((d["p_h"] >= 0.9) & (d["o"] == 0)) | ((d["p_h"] <= 0.1) & (d["o"] == 1))
d["wrong_a"] = ((d["p_a"] >= 0.9) & (d["o"] == 0)) | ((d["p_a"] <= 0.1) & (d["o"] == 1))

QS = [0, .05, .25, .5, .75, .95, 1]


def dist_table(col):
    rows = {}
    for q, sub in d.groupby("EXT_q", observed=True):
        s = sub[col].values
        r = {f"q{int(p*100)}": float(np.quantile(s, p)) for p in QS}
        r["mean"] = float(s.mean())
        r["n"] = int(len(s))
        rows[q] = r
    return pd.DataFrame(rows).T


dist_ga = dist_table("G_a")
dist_gl = dist_table("G_log")

share = (d.groupby("EXT_q", observed=True)
          .agg(EXT_a_min=("EXT_a", "min"), EXT_a_max=("EXT_a", "max"),
               n=("wrong_h", "size"),
               human_conf_wrong=("wrong_h", "mean"),
               baseline_a_conf_wrong=("wrong_a", "mean")))
share["ratio_human_over_baseline"] = (share["human_conf_wrong"]
                                      / share["baseline_a_conf_wrong"])

by_group = (d.groupby(["GRP", "EXT_q"], observed=True)
             .agg(n=("wrong_h", "size"),
                  human_conf_wrong=("wrong_h", "mean"),
                  baseline_a_conf_wrong=("wrong_a", "mean"))
             .reset_index().set_index(["GRP", "EXT_q"]))
overall_group = (d.groupby("GRP")
                  .agg(n=("wrong_h", "size"),
                       human_conf_wrong=("wrong_h", "mean"),
                       baseline_a_conf_wrong=("wrong_a", "mean")))

# --------------------------------------------------------------- figure
fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
x = np.arange(4)
ax = axes[0]
ax.axhline(0, color="#999", lw=.8)
ax.plot(x, dist_ga["mean"], "o-", color="#1b6ca8", label="mean $G_a$ (Brier)")
ax.set_xticks(x); ax.set_xticklabels(dist_ga.index)
ax.set_xlabel("quartile of $EXT_a$"); ax.set_ylabel("mean $G_a$", color="#1b6ca8")
ax.tick_params(axis="y", labelcolor="#1b6ca8")
ax2 = ax.twinx()
ax2.plot(x, dist_gl["mean"], "s--", color="#c1121f", label="mean $G_{log}$")
ax2.set_ylabel("mean $G_{log}$", color="#c1121f")
ax2.tick_params(axis="y", labelcolor="#c1121f")
ax.set_title("Human's return by extremization quartile\n(positive = human better)",
             fontsize=10)
for a_, ser, colr in ((ax, dist_ga["mean"], "#1b6ca8"), (ax2, dist_gl["mean"], "#c1121f")):
    for i in (0, 3):
        a_.annotate(f"{ser.iloc[i]:+.3f}", (x[i], ser.iloc[i]),
                    textcoords="offset points", xytext=(0, -14 if colr == "#c1121f" else 8),
                    ha="center", fontsize=7.5, color=colr)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="lower left")

ax = axes[1]
wbar = 0.38
ax.bar(x - wbar/2, 100*share["human_conf_wrong"], wbar, color="#1b6ca8", label="human")
ax.bar(x + wbar/2, 100*share["baseline_a_conf_wrong"], wbar, color="#8d99ae",
       label="baseline (a)")
ax.set_xticks(x); ax.set_xticklabels(share.index)
ax.set_xlabel("quartile of $EXT_a$")
ax.set_ylabel("% of rows confidently wrong")
ax.set_title("Confidently wrong: $p\\geq0.9$ with $o=0$, or $p\\leq0.1$ with $o=1$",
             fontsize=10)
ax.legend(fontsize=8)
fig.suptitle("Post-hoc diagnostic for the H4 Brier / log-score reversal "
             "(not pre-registered)", fontsize=11)
fig.tight_layout()
fig.savefig(CFG.FIGDIR / "full_posthoc_ext_quartiles.png", dpi=150)
plt.close(fig)

# --------------------------------------------------------------- section
S = []
def w(s=""):
    S.append(s)

w(MARKER_START)
w("## Post-hoc diagnostics (not pre-registered)")
w()
w("**Specified after the results were seen (Amendment 3, 2026-09-06). Diagnostic only: "
  "no pre-registered model was refitted, no estimate above changes, and nothing in this "
  "section is a hypothesis test.** It exists to locate where the two scoring rules "
  "disagree, not to decide between them.")
w()
w("The reversal being diagnosed: the H4 core quantity `EXT_a_z` is "
  "**+0.02826 [0.02518, 0.03135]** under Brier (§9, primary) and "
  "**−0.02190 [−0.03282, −0.01098]** under the log score (§11.7.2), neither interval "
  "containing zero. All rows below are the primary analysis rows "
  f"({len(d):,}), split into quartiles of `EXT_a`.")
w()
w(f"Quartile cut points of `EXT_a`: {edges[0]:.4f} / {edges[1]:.4f} / {edges[2]:.4f} / "
  f"{edges[3]:.4f} / {edges[4]:.4f}.")
w()
w("### Distribution of `G_a` (Brier) by `EXT_a` quartile")
w()
w(md_table(dist_ga, floatfmt="%.4f"))
w()
w("### Distribution of `G_log` (log score) by `EXT_a` quartile")
w()
w(md_table(dist_gl, floatfmt="%.4f"))
w()
w("### Confidently-wrong share by `EXT_a` quartile")
w()
w("A row counts as confidently wrong when the forecast is at or beyond 0.9 on the wrong "
  "side of the outcome: `p >= 0.9` with `o = 0`, or `p <= 0.1` with `o = 1`. Shares are "
  "proportions of rows in the quartile.")
w()
w(md_table(share, floatfmt="%.4f"))
w()
w("### The same shares by group")
w()
w(md_table(by_group, floatfmt="%.4f"))
w()
w("Group totals across all quartiles:")
w()
w(md_table(overall_group, floatfmt="%.4f"))
w()
w("![Post-hoc EXT quartile diagnostic](figures/full_posthoc_ext_quartiles.png)")
w()
w("### What the tables show")
w()
q1, q2, q3, q4 = list(share.index)
w(f"**The reversal is a {q1}/{q4} swap.** Under Brier the most-extremizing quartile "
  f"{q4} (mean `G_a` {dist_ga.loc[q4,'mean']:+.4f}) is *better* than the least-extremizing "
  f"{q1} ({dist_ga.loc[q1,'mean']:+.4f}). Under the log score the order flips: {q4} "
  f"(mean `G_log` {dist_gl.loc[q4,'mean']:+.4f}) is far *worse* than {q1} "
  f"({dist_gl.loc[q1,'mean']:+.4f}). The two middle quartiles agree under both rules "
  f"({q2} and {q3} are the best two either way). That single swap at the extremes is the "
  "reversal seen in the fitted coefficients, visible here without any model.")
w()
w(f"**The mechanism is a thin tail of confident errors.** The human confidently-wrong "
  f"share rises monotonically across quartiles, "
  f"{100*share['human_conf_wrong'].iloc[0]:.2f}% → "
  f"{100*share['human_conf_wrong'].iloc[1]:.2f}% → "
  f"{100*share['human_conf_wrong'].iloc[2]:.2f}% → "
  f"**{100*share['human_conf_wrong'].iloc[-1]:.2f}%** in {q4}. Baseline (a) on the same "
  f"rows goes the other way, {100*share['baseline_a_conf_wrong'].iloc[0]:.2f}% → "
  f"{100*share['baseline_a_conf_wrong'].iloc[-1]:.2f}%: by construction the model is never "
  f"confidently wrong in {q4}, because {q4} is where the human is far more extreme than a "
  "model that was not extreme to begin with.")
w()
sp = float(overall_group.loc["S", "human_conf_wrong"])
sb = float(overall_group.loc["S", "baseline_a_conf_wrong"])
pp = float(overall_group.loc["P", "human_conf_wrong"])
pb = float(overall_group.loc["P", "baseline_a_conf_wrong"])
w(f"**The two groups behave oppositely.** Superforecasters are confidently wrong on "
  f"{100*sp:.2f}% of their rows against baseline (a)'s {100*sb:.2f}% on those same rows — "
  f"they are confidently wrong *less* often than the model. Public forecasters are "
  f"confidently wrong on {100*pp:.2f}% against {100*pb:.2f}%, roughly "
  f"{pp/pb:.0f}× the model's rate. The log-score penalty therefore falls overwhelmingly on "
  "the public group, and the negative log-score `EXT_a` coefficient should be read with "
  "that in mind.")
w()
w("The log score is unbounded below and the Brier score is bounded, so a single "
  "confident error costs far more under the log score than any number of small "
  "improvements can repay. Read the two coefficient signs together with these tables "
  "rather than separately. This section does not establish which rule the study should "
  "prefer; §5.4 and §7.2 are unamended and the primary H4 remains the Brier fit.")
w()
w(MARKER_END)

section = "\n".join(S)
path = CFG.DOCS / "forecast_full_REPORT.md"
text = path.read_text()
text = re.sub(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END) + r"\n*",
              "", text, flags=re.S)
anchor = "---\n\n## Stop\n"
assert anchor in text, "closing section not found; report structure changed"
text = text.replace(anchor, "---\n\n" + section + "\n\n" + anchor, 1)
path.write_text(text)
print("inserted post-hoc section into", path)
print(share.to_string())
print()
print(overall_group.to_string())
