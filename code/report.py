"""Shared markdown/report helpers (used by the full run)."""
import numpy as np
import pandas as pd


def md_table(df, floatfmt="%.4f", index=True):
    d = df.copy()
    if index:
        d = d.reset_index()
    cols = list(d.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in d.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("—" if not np.isfinite(v) else floatfmt % v)
            elif isinstance(v, (bool, np.bool_)):
                cells.append("yes" if v else "no")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def quantiles(s, qs=(0, .05, .25, .5, .75, .95, 1)):
    out = {f"q{int(q*100)}": float(np.quantile(s, q)) for q in qs}
    out["mean"] = float(np.mean(s))
    out["sd"] = float(np.std(s, ddof=1))
    return pd.Series(out)


def ci_str(v, lo, hi, f="%.4f"):
    return f"{f % v} [{f % lo}, {f % hi}]"
