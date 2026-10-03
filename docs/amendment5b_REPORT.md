# SPEC v3 Amendment 5b: encompassing by question source

Post-results in origin; reading locked in specs/forecast_spec_v3.md (commit `751e0fb`) before computation. Nothing here changes a v1 or v2 number. The pooled Section 4.2 (v1 §7) results are unchanged by this amendment.

## Result against the locked reading

- **Superforecaster median**: dataset 2.16 [1.04, 3.28], market 1.12 [0.13, 2.11]. Branch: **both positive: the increment is not fully explained by access to newer data points (still not evidence of judgment)**.
- **Public median**: dataset 1.08 [0.26, 1.90], market 1.94 [0.34, 3.55]. Branch: **both positive: the increment is not fully explained by access to newer data points (still not evidence of judgment)**.

## Locked reading (restated from SPEC v3)

- Dataset coefficient positive and market interval includes zero: the increment is where the information gap is. The paper's main claim is restated as "relative to a model without news, on questions where humans could retrieve newer data".
- Both positive: the increment is not fully explained by access to newer data points, since on market questions both sides shared the freeze price. This is still not evidence of judgment; the paper says so.
- Market positive and dataset interval includes zero: contrary to the information-gap account. Reported in the main text as such, not in a footnote.
- The pooled Section 4.2 numbers are not changed by this amendment.

## Estimates

Target level, logistic, `o ~ logit(p_a) + [logit(p_h) - logit(p_a)]`, question-clustered SEs, benchmark (a) unchanged (`Claude-3-5-Sonnet-20240620 (zero shot with freeze values)`), groups fit separately. Function: `models.encompassing` (v1), imported.

Sources: **521 dataset targets on 105 questions; 57 market targets on 57 questions.** No question mixes sources.

**Primary, clip (0.01, 0.99):**

| source | group | coef_human_minus_model | ci_lo | ci_hi | coef_logit_p_a | p_a_ci_lo | p_a_ci_hi | n_targets | n_questions | clipped_model | clipped_human |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dataset | S | 2.16 | 1.04 | 3.28 | 2.17 | 0.83 | 3.51 | 521 | 105 | 4 | 145 |
| dataset | P | 1.08 | 0.26 | 1.90 | 2.12 | 1.33 | 2.91 | 521 | 105 | 4 | 0 |
| market | S | 1.12 | 0.13 | 2.11 | 0.82 | 0.32 | 1.33 | 57 | 57 | 3 | 15 |
| market | P | 1.94 | 0.34 | 3.55 | 1.33 | 0.42 | 2.25 | 57 | 57 | 3 | 0 |

**Sensitivity, clip (0.001, 0.999):**

| source | group | coef_human_minus_model | ci_lo | ci_hi | coef_logit_p_a | p_a_ci_lo | p_a_ci_hi | n_targets | n_questions | clipped_model | clipped_human |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dataset | S | 2.15 | 1.02 | 3.29 | 2.16 | 0.79 | 3.53 | 521 | 105 | 0 | 124 |
| dataset | P | 1.08 | 0.26 | 1.90 | 2.12 | 1.33 | 2.91 | 521 | 105 | 0 | 0 |
| market | S | 1.07 | 0.10 | 2.05 | 0.78 | 0.25 | 1.31 | 57 | 57 | 0 | 12 |
| market | P | 1.94 | 0.33 | 3.55 | 1.34 | 0.42 | 2.25 | 57 | 57 | 0 | 0 |

`clipped_model` / `clipped_human` count targets where benchmark (a) / the human median falls outside the clip bounds. The market subset has only 57 targets across 57 market questions (one target per question, so clustering is nominal there); its intervals are correspondingly wide.

## Checklist

- Spec commit: `751e0fb68d0d8131044cea92b88375bdf865c499` (specs/forecast_spec_v3.md, committed before any v3 computation; not pushed). Repo HEAD at run: `751e0fb68d0d8131044cea92b88375bdf865c499`.
- Locked reading: restated above.
- Branch, superforecaster median: B — both positive: the increment is not fully explained by access to newer data points (still not evidence of judgment).
- Branch, public median: B — both positive: the increment is not fully explained by access to newer data points (still not evidence of judgment).
- Reproduction check (untouched v1 H2 path, pooled, clip (0.01, 0.99)): S 1.79 [1.04, 2.53] vs locked 1.79 [1.04, 2.53] — match; P 0.97 [0.24, 1.70] vs locked 0.97 [0.24, 1.70] — match.
