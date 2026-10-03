# SPEC v3 Amendment 6: out-of-sample combination

Post-results in origin; reading locked in specs/forecast_spec_v3.md (commit `751e0fb`) before computation. No v1 or v2 number changes.

## Locked reading (restated from SPEC v3)

- "The human median carries a deployable increment" is claimed only if human + M1 beats M1 alone AND beats M1 + Mens on the primary score, with both bootstrap intervals excluding zero. Beating M1 alone is not enough; any second forecast improves a single model.
- human + Mens versus Mens alone is the co-primary question: whether the human median adds to the ensemble. This is the decision version of the v2 reference curve.
- If the log score and Brier disagree on a claim, the paper takes no side and states the disagreement in one sentence with a pointer to the companion methods paper.
- The public and superforecaster results are read separately. A claim that holds for superforecasters and not for the public is stated as a claim about the superforecaster median under tournament and web-search conditions, not about "humans".
- If a fitted weight's fold-to-fold SD exceeds 0.2, the optimized combiners (C3, C4) are reported as descriptive only and the equal-weight rows carry the claim.
- If the 7-person public median behaves like the superforecaster median against Mens, the superforecaster exception in v2 is read as a sample-size effect, not a group effect.
- No switching rules by disagreement (DIS) are fitted. That question was H3 and is closed.

## Result against the locked reading

- Weight-stability rule: no constrained C3/C4 weight has fold-to-fold SD > 0.2, so C1–C4 can all carry claims (max constrained SD = 0.099).
- Deployable increment, superforecaster median: deployable increment claimed under C1, C2, C3, C4 (human + M1 beats M1 alone and M1 + Mens on log score, both intervals above zero).
- Deployable increment, public median: no deployable increment claimed — under none of C1, C2, C3, C4 does human + M1 beat both M1 alone and M1 + Mens on log score with both intervals above zero.
- Co-primary, superforecaster median: human + Mens beats Mens alone on log score under C1, C2, C3, C4.
- Co-primary, public median: human + Mens beats Mens alone on log score under C1, C2, C3, C4.
- Log score and Brier agree on every claim above.
- Noise control: the superforecaster median's log-score improvement over Mens (human + Mens vs Mens) lies inside the 200-draw 95% band of the 7-person public median's improvement under none of C1, C2, C3, C4. By the operationalization below, the 7-person median does not behave like the superforecaster median against Mens, so the v2 superforecaster exception is not read as a sample-size effect.
- The deployable-increment claim holds for superforecasters and not for the public, so it is stated as a claim about the superforecaster median under tournament and web-search conditions, not about "humans".

Descriptive notes (added after review; no new claims, no number changed):

- For the superforecaster median, C3 and C4 put weight 1.000 on the human in every fold (H_S+M1 and H_S+Mens), so the best fitted pool is the superforecaster median alone. H_S alone vs M1: log +0.097 [+0.060, +0.140], Brier +0.035 [+0.020, +0.052]. H_S alone vs H_S+M1 · C1: log +0.034 [+0.020, +0.050], Brier +0.011 [+0.005, +0.017]. H_S alone vs H_S+M1 · C2: log +0.025 [+0.012, +0.039], Brier +0.008 [+0.003, +0.014].
- Fitted C3u weights (secondary), mean over the 5 folds: H_S+M1 w(human) 1.236 (fold SD 0.065), w(M1) -0.170 (fold SD 0.057); H_P+M1 w(human) 0.523 (fold SD 0.086), w(M1) 0.503 (fold SD 0.090).
- Mens alone scores worse than M1 (log score -0.511 vs -0.448; Brier 0.173 vs 0.153), so M1+Mens under equal weights is worse than M1 (C1 log -0.470, C2 log -0.461) and "beats M1+Mens" is the weaker of the two conditions; the binding condition is "beats M1".
- Mnews alone: log score -0.469, Brier 0.159; Mnews vs M1: log -0.021 [-0.069, +0.020], Brier -0.006 [-0.026, +0.010].

## Setup

- 578 targets on 162 questions; one row per target. Sources: M1 = benchmark (a) `Claude-3-5-Sonnet-20240620 (zero shot with freeze values)`; Mnews = `Claude-3-5-Sonnet-20240620 (superforecaster with news 1)`; Mens = median of the 33 matched variants other than M1 (v2 Amendment 2 reference; contributors per target 29–33); H_S, H_P = group medians.
- Folds: v2 cross-fit folds (5, by question, seed 20260908). Check: the v2 cross-fitted log-score gain for M1 recomputed on these folds equals the stored v2 point estimate S 0.097940 vs 0.097940; P 0.019478 vs 0.019478.
- Scores: log score = mean log probability on the outcome, probabilities clipped to (0.01, 0.99) (v1/v2 convention; primary); Brier = mean squared error on the unclipped probability (clipped to [0, 1] only for C3u). Differences are written as the improvement of the first system over the second: log a − log b, Brier b − a; positive favors the first.
- Combiners: C1 mean of probabilities; C2 mean of logits (inputs clipped as above); C3 linear weight w ∈ [0, 1] on the first source, 1 − w on the second, minimizing training-fold Brier (closed form, then clipped); C3u unconstrained linear weights, no intercept, least squares (secondary; this reading of the spec's "unconstrained weights" is not fixed by the spec, chosen here post-spec and flagged); C4 log-pool weight w ∈ [0, 1] minimizing training-fold log score. Weights frozen on the test fold.
- Noise control N7: median of 7 public forecasts drawn without replacement on each target (public forecasters per target 40–63; superforecasters per target median 7, range 3–29). Seed 20260906; draw 1 is the reported draw and enters the bootstrap; 200 draws give the median and 2.5–97.5% band.
- Intervals: question-level cluster bootstrap, 2000 draws, seed 20260906; within each draw duplicated questions are distinct clusters, folds are reassigned on the draw's clusters with the v2 fold rule (as in the v2 cross-fit bootstrap), and C3/C3u/C4 weights are refit. Percentile intervals.

## Systems: pooled out-of-sample scores

| system | log_score | brier |
|---|---|---|
| M1 | -0.448 | 0.153 |
| Mens | -0.511 | 0.173 |
| Mnews | -0.469 | 0.159 |
| H_S | -0.351 | 0.118 |
| H_P | -0.466 | 0.154 |
| H_S+M1 · C1 | -0.385 | 0.129 |
| H_S+M1 · C2 | -0.375 | 0.127 |
| H_S+M1 · C3 | -0.351 | 0.118 |
| H_S+M1 · C3u | -0.349 | 0.118 |
| H_S+M1 · C4 | -0.351 | 0.118 |
| H_P+M1 · C1 | -0.440 | 0.146 |
| H_P+M1 · C2 | -0.435 | 0.146 |
| H_P+M1 · C3 | -0.444 | 0.148 |
| H_P+M1 · C3u | -0.446 | 0.149 |
| H_P+M1 · C4 | -0.439 | 0.148 |
| H_S+Mens · C1 | -0.416 | 0.134 |
| H_S+Mens · C2 | -0.385 | 0.127 |
| H_S+Mens · C3 | -0.351 | 0.118 |
| H_S+Mens · C3u | -0.348 | 0.118 |
| H_S+Mens · C4 | -0.351 | 0.118 |
| H_P+Mens · C1 | -0.473 | 0.156 |
| H_P+Mens · C2 | -0.469 | 0.154 |
| H_P+Mens · C3 | -0.470 | 0.155 |
| H_P+Mens · C3u | -0.472 | 0.155 |
| H_P+Mens · C4 | -0.467 | 0.155 |
| M1+Mens · C1 | -0.470 | 0.158 |
| M1+Mens · C2 | -0.461 | 0.156 |
| M1+Mens · C3 | -0.451 | 0.154 |
| M1+Mens · C3u | -0.448 | 0.154 |
| M1+Mens · C4 | -0.449 | 0.154 |
| N7+M1 · C1 | -0.451 | 0.151 |
| N7+M1 · C2 | -0.448 | 0.151 |
| N7+M1 · C3 | -0.445 | 0.150 |
| N7+M1 · C3u | -0.446 | 0.151 |
| N7+M1 · C4 | -0.441 | 0.150 |
| N7+Mens · C1 | -0.485 | 0.161 |
| N7+Mens · C2 | -0.482 | 0.161 |
| N7+Mens · C3 | -0.488 | 0.163 |
| N7+Mens · C3u | -0.490 | 0.164 |
| N7+Mens · C4 | -0.485 | 0.162 |
| H_S+M1+Mens · C1 | -0.420 | 0.138 |
| H_S+M1+Mens · C2 | -0.396 | 0.132 |
| H_P+M1+Mens · C1 | -0.457 | 0.151 |
| H_P+M1+Mens · C2 | -0.448 | 0.149 |

## Deployable increment: human + M1 vs M1 alone, and vs M1 + Mens

**Superforecaster median**

| comparison | d_log | log_ci | d_brier | brier_ci |
|---|---|---|---|---|
| H_S+M1 · C1  vs  M1 | +0.063 | [+0.040, +0.090] | +0.024 | [+0.015, +0.035] |
| H_S+M1 · C1  vs  M1+Mens · C1 | +0.085 | [+0.066, +0.105] | +0.029 | [+0.021, +0.038] |
| H_S+M1 · C2  vs  M1 | +0.073 | [+0.047, +0.102] | +0.027 | [+0.017, +0.038] |
| H_S+M1 · C2  vs  M1+Mens · C2 | +0.086 | [+0.064, +0.108] | +0.029 | [+0.020, +0.039] |
| H_S+M1 · C3  vs  M1 | +0.097 | [+0.060, +0.140] | +0.035 | [+0.020, +0.052] |
| H_S+M1 · C3  vs  M1+Mens · C3 | +0.100 | [+0.060, +0.142] | +0.036 | [+0.020, +0.052] |
| H_S+M1 · C3u  vs  M1 | +0.099 | [+0.062, +0.148] | +0.035 | [+0.021, +0.055] |
| H_S+M1 · C3u  vs  M1+Mens · C3u | +0.100 | [+0.057, +0.142] | +0.036 | [+0.020, +0.051] |
| H_S+M1 · C4  vs  M1 | +0.097 | [+0.060, +0.140] | +0.035 | [+0.020, +0.052] |
| H_S+M1 · C4  vs  M1+Mens · C4 | +0.099 | [+0.060, +0.141] | +0.035 | [+0.020, +0.052] |

**Public median**

| comparison | d_log | log_ci | d_brier | brier_ci |
|---|---|---|---|---|
| H_P+M1 · C1  vs  M1 | +0.008 | [-0.014, +0.034] | +0.007 | [-0.002, +0.016] |
| H_P+M1 · C1  vs  M1+Mens · C1 | +0.030 | [+0.013, +0.048] | +0.012 | [+0.004, +0.020] |
| H_P+M1 · C2  vs  M1 | +0.013 | [-0.008, +0.036] | +0.008 | [-0.001, +0.017] |
| H_P+M1 · C2  vs  M1+Mens · C2 | +0.026 | [+0.008, +0.043] | +0.010 | [+0.002, +0.018] |
| H_P+M1 · C3  vs  M1 | +0.004 | [-0.007, +0.031] | +0.005 | [-0.001, +0.017] |
| H_P+M1 · C3  vs  M1+Mens · C3 | +0.007 | [-0.006, +0.033] | +0.005 | [-0.001, +0.017] |
| H_P+M1 · C3u  vs  M1 | +0.002 | [-0.015, +0.031] | +0.004 | [-0.002, +0.016] |
| H_P+M1 · C3u  vs  M1+Mens · C3u | +0.002 | [-0.015, +0.016] | +0.005 | [-0.001, +0.012] |
| H_P+M1 · C4  vs  M1 | +0.009 | [-0.003, +0.035] | +0.005 | [-0.000, +0.018] |
| H_P+M1 · C4  vs  M1+Mens · C4 | +0.011 | [-0.002, +0.036] | +0.006 | [-0.000, +0.018] |

## Co-primary: human + Mens vs Mens alone

| comparison | d_log | log_ci | d_brier | brier_ci |
|---|---|---|---|---|
| H_S+Mens · C1  vs  Mens | +0.095 | [+0.075, +0.115] | +0.039 | [+0.029, +0.049] |
| H_S+Mens · C2  vs  Mens | +0.126 | [+0.101, +0.153] | +0.047 | [+0.036, +0.059] |
| H_S+Mens · C3  vs  Mens | +0.161 | [+0.124, +0.197] | +0.055 | [+0.040, +0.070] |
| H_S+Mens · C3u  vs  Mens | +0.164 | [+0.125, +0.204] | +0.055 | [+0.041, +0.072] |
| H_S+Mens · C4  vs  Mens | +0.161 | [+0.125, +0.197] | +0.055 | [+0.040, +0.070] |
| H_P+Mens · C1  vs  Mens | +0.038 | [+0.019, +0.057] | +0.017 | [+0.008, +0.027] |
| H_P+Mens · C2  vs  Mens | +0.043 | [+0.023, +0.063] | +0.019 | [+0.009, +0.029] |
| H_P+Mens · C3  vs  Mens | +0.042 | [+0.016, +0.083] | +0.018 | [+0.007, +0.036] |
| H_P+Mens · C3u  vs  Mens | +0.039 | [+0.012, +0.082] | +0.018 | [+0.007, +0.036] |
| H_P+Mens · C4  vs  Mens | +0.044 | [+0.018, +0.083] | +0.019 | [+0.008, +0.036] |

## Other comparisons

| comparison | d_log | log_ci | d_brier | brier_ci |
|---|---|---|---|---|
| Mens  vs  M1 | -0.063 | [-0.094, -0.032] | -0.020 | [-0.032, -0.008] |
| Mnews  vs  M1 | -0.021 | [-0.069, +0.020] | -0.006 | [-0.026, +0.010] |
| H_S  vs  M1 | +0.097 | [+0.060, +0.140] | +0.035 | [+0.020, +0.052] |
| H_P  vs  M1 | -0.018 | [-0.060, +0.027] | -0.001 | [-0.019, +0.017] |
| H_S  vs  Mens | +0.161 | [+0.125, +0.197] | +0.055 | [+0.040, +0.070] |
| H_P  vs  Mens | +0.045 | [+0.005, +0.085] | +0.019 | [+0.001, +0.037] |
| H_S+M1+Mens · C1  vs  M1+Mens · C1 | +0.050 | [+0.037, +0.064] | +0.020 | [+0.014, +0.027] |
| H_S+M1+Mens · C2  vs  M1+Mens · C2 | +0.065 | [+0.048, +0.082] | +0.024 | [+0.017, +0.032] |
| H_P+M1+Mens · C1  vs  M1+Mens · C1 | +0.013 | [+0.001, +0.025] | +0.007 | [+0.002, +0.013] |
| H_P+M1+Mens · C2  vs  M1+Mens · C2 | +0.013 | [+0.001, +0.026] | +0.007 | [+0.002, +0.013] |
| H_S+M1+Mens · C1  vs  H_S+Mens · C1 | -0.004 | [-0.012, +0.003] | -0.004 | [-0.007, -0.000] |
| H_S+M1+Mens · C2  vs  H_S+Mens · C2 | -0.011 | [-0.020, -0.003] | -0.005 | [-0.009, -0.002] |
| H_P+M1+Mens · C1  vs  H_P+Mens · C1 | +0.016 | [+0.007, +0.025] | +0.005 | [+0.000, +0.009] |
| H_P+M1+Mens · C2  vs  H_P+Mens · C2 | +0.021 | [+0.009, +0.032] | +0.006 | [+0.000, +0.010] |

## Noise control (N7, 7-person public median)

Draw 1 with bootstrap intervals:

| comparison | d_log | log_ci | d_brier | brier_ci |
|---|---|---|---|---|
| N7+M1 · C1  vs  M1 | -0.004 | [-0.027, +0.023] | +0.002 | [-0.008, +0.012] |
| N7+M1 · C1  vs  M1+Mens · C1 | +0.019 | [-0.002, +0.039] | +0.007 | [-0.002, +0.016] |
| N7+Mens · C1  vs  Mens | +0.027 | [+0.006, +0.047] | +0.012 | [+0.002, +0.022] |
| N7+M1 · C2  vs  M1 | -0.000 | [-0.024, +0.025] | +0.002 | [-0.008, +0.012] |
| N7+M1 · C2  vs  M1+Mens · C2 | +0.013 | [-0.009, +0.035] | +0.005 | [-0.005, +0.015] |
| N7+Mens · C2  vs  Mens | +0.029 | [+0.004, +0.053] | +0.012 | [+0.001, +0.023] |
| N7+M1 · C3  vs  M1 | +0.003 | [-0.006, +0.020] | +0.003 | [-0.001, +0.011] |
| N7+M1 · C3  vs  M1+Mens · C3 | +0.006 | [-0.005, +0.022] | +0.004 | [-0.001, +0.011] |
| N7+Mens · C3  vs  Mens | +0.023 | [+0.006, +0.050] | +0.011 | [+0.003, +0.023] |
| N7+M1 · C3u  vs  M1 | +0.002 | [-0.012, +0.028] | +0.002 | [-0.003, +0.012] |
| N7+M1 · C3u  vs  M1+Mens · C3u | +0.002 | [-0.011, +0.012] | +0.002 | [-0.001, +0.006] |
| N7+Mens · C3u  vs  Mens | +0.021 | [+0.004, +0.053] | +0.009 | [+0.002, +0.023] |
| N7+M1 · C4  vs  M1 | +0.007 | [-0.002, +0.023] | +0.003 | [-0.001, +0.011] |
| N7+M1 · C4  vs  M1+Mens · C4 | +0.008 | [-0.002, +0.025] | +0.004 | [-0.001, +0.011] |
| N7+Mens · C4  vs  Mens | +0.026 | [+0.010, +0.052] | +0.011 | [+0.004, +0.023] |

Across 200 draws, log-score improvement (median [2.5%, 97.5%]), next to the two group medians:

| combiner | comparison | n7 | H_S | H_P |
|---|---|---|---|---|
| C1 | N7 + M1 vs M1 | -0.004 [-0.014, +0.008] | +0.063 | +0.008 |
| C1 | N7 + M1 vs M1 + Mens | +0.019 [+0.009, +0.030] | +0.085 | +0.030 |
| C1 | N7 + Mens vs Mens | +0.025 [+0.016, +0.036] | +0.095 | +0.038 |
| C2 | N7 + M1 vs M1 | +0.002 [-0.010, +0.015] | +0.073 | +0.013 |
| C2 | N7 + M1 vs M1 + Mens | +0.015 [+0.003, +0.028] | +0.086 | +0.026 |
| C2 | N7 + Mens vs Mens | +0.029 [+0.016, +0.043] | +0.126 | +0.043 |
| C3 | N7 + M1 vs M1 | +0.002 [-0.002, +0.008] | +0.097 | +0.004 |
| C3 | N7 + M1 vs M1 + Mens | +0.005 [+0.001, +0.011] | +0.100 | +0.007 |
| C3 | N7 + Mens vs Mens | +0.020 [+0.010, +0.035] | +0.161 | +0.042 |
| C3u | N7 + M1 vs M1 | +0.002 [-0.001, +0.005] | +0.099 | +0.002 |
| C3u | N7 + M1 vs M1 + Mens | +0.002 [-0.000, +0.005] | +0.100 | +0.002 |
| C3u | N7 + Mens vs Mens | +0.020 [+0.012, +0.032] | +0.164 | +0.039 |
| C4 | N7 + M1 vs M1 | +0.006 [-0.001, +0.014] | +0.097 | +0.009 |
| C4 | N7 + M1 vs M1 + Mens | +0.008 [+0.000, +0.015] | +0.099 | +0.011 |
| C4 | N7 + Mens vs Mens | +0.025 [+0.013, +0.038] | +0.161 | +0.044 |

Operationalization of "behaves like the superforecaster median against Mens" (not fixed by the spec; chosen here post-spec and flagged): the superforecaster median's point log-score improvement of human + Mens over Mens lies inside the 200-draw 2.5–97.5% band of the same quantity for N7, for each claim-carrying combiner.

## Fitted weights: fold-to-fold variation (point fit)

| system | weight | mean | sd | min | max |
|---|---|---|---|---|---|
| H_S+M1 · C3 | w(first) | 1.000 | 0.000 | 1.000 | 1.000 |
| H_S+M1 · C3u | w(first) | 1.236 | 0.065 | 1.150 | 1.320 |
| H_S+M1 · C3u | w(second) | -0.170 | 0.057 | -0.222 | -0.090 |
| H_S+M1 · C4 | w(first) | 1.000 | 0.000 | 1.000 | 1.000 |
| H_P+M1 · C3 | w(first) | 0.476 | 0.099 | 0.320 | 0.563 |
| H_P+M1 · C3u | w(first) | 0.523 | 0.086 | 0.373 | 0.583 |
| H_P+M1 · C3u | w(second) | 0.503 | 0.090 | 0.433 | 0.654 |
| H_P+M1 · C4 | w(first) | 0.418 | 0.085 | 0.291 | 0.505 |
| H_S+Mens · C3 | w(first) | 1.000 | 0.000 | 1.000 | 1.000 |
| H_S+Mens · C3u | w(first) | 1.166 | 0.041 | 1.136 | 1.237 |
| H_S+Mens · C3u | w(second) | -0.103 | 0.021 | -0.122 | -0.075 |
| H_S+Mens · C4 | w(first) | 1.000 | 0.000 | 1.000 | 1.000 |
| H_P+Mens · C3 | w(first) | 0.789 | 0.099 | 0.630 | 0.874 |
| H_P+Mens · C3u | w(first) | 0.993 | 0.123 | 0.856 | 1.121 |
| H_P+Mens · C3u | w(second) | 0.106 | 0.103 | 0.005 | 0.248 |
| H_P+Mens · C4 | w(first) | 0.780 | 0.095 | 0.625 | 0.865 |
| M1+Mens · C3 | w(first) | 0.962 | 0.065 | 0.847 | 1.000 |
| M1+Mens · C3u | w(first) | 0.882 | 0.110 | 0.713 | 0.991 |
| M1+Mens · C3u | w(second) | 0.005 | 0.082 | -0.085 | 0.134 |
| M1+Mens · C4 | w(first) | 0.973 | 0.060 | 0.865 | 1.000 |
| N7+M1 · C3 | w(first) | 0.285 | 0.045 | 0.222 | 0.344 |
| N7+M1 · C3u | w(first) | 0.223 | 0.034 | 0.177 | 0.268 |
| N7+M1 · C3u | w(second) | 0.726 | 0.038 | 0.676 | 0.781 |
| N7+M1 · C4 | w(first) | 0.251 | 0.040 | 0.195 | 0.304 |
| N7+Mens · C3 | w(first) | 0.492 | 0.067 | 0.395 | 0.582 |
| N7+Mens · C3u | w(first) | 0.400 | 0.080 | 0.332 | 0.516 |
| N7+Mens · C3u | w(second) | 0.534 | 0.065 | 0.437 | 0.615 |
| N7+Mens · C4 | w(first) | 0.426 | 0.055 | 0.346 | 0.502 |

`w(first)` is the weight on the first-named source (the human, N7 or M1). The SD rule is applied to the constrained C3 and C4 weights; C3u is secondary and reported only.

## Checklist

- Spec commit: `751e0fb68d0d8131044cea92b88375bdf865c499`. Repo HEAD at run: `abdc4aca32ea4a8fbad6473f4e9057e56db9d298`. Amendment 6 results not committed.
- Locked reading: restated above.
- Branch, deployable increment, superforecaster median: deployable increment claimed under C1, C2, C3, C4 (human + M1 beats M1 alone and M1 + Mens on log score, both intervals above zero).
- Branch, co-primary, superforecaster median: human + Mens beats Mens alone on log score under C1, C2, C3, C4.
- Branch, deployable increment, public median: no deployable increment claimed — under none of C1, C2, C3, C4 does human + M1 beat both M1 alone and M1 + Mens on log score with both intervals above zero.
- Branch, co-primary, public median: human + Mens beats Mens alone on log score under C1, C2, C3, C4.
- Reproduction check (untouched v1 H2 path, pooled, clip (0.01, 0.99)): S 1.79 [1.04, 2.53] vs locked 1.79 [1.04, 2.53] — match; P 0.97 [0.24, 1.70] vs locked 0.97 [0.24, 1.70] — match.
- Runtime 23s.
