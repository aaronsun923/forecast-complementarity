# v9 checks

**Computed after Amendment 6; reparameterization of the locked v1 H2 fit, no new model.** Read-only: no locked number is changed, nobody is dropped. Not committed.

## 1. Reverse encompassing (model increment given the human median)

From the locked v1 H2 fit `o ~ logit(p_a) + [logit(p_h) − logit(p_a)]` (same data, clip, question clustering; the fit is the `models.encompassing` call repeated to keep its covariance, and its coefficients and intervals are asserted equal to `models.encompassing`): the fit equals `o ~ (b_pa − b_h)·logit(p_a) + b_h·logit(p_h)`, so `b_model = b_pa − b_h` is the coefficient on the model given the human median. 95% interval from the same fit's question-clustered covariance: Var = V(b_pa) + V(b_h) − 2Cov.

Check: pooled primary S 1.5583 − 1.7892 = -0.2309 (expected 1.5583 − 1.7892 = -0.2309); P 1.6960 − 0.9718 = 0.7242 (expected 1.6960 − 0.9718 = 0.7242). Match.

**clip (0.01, 0.99), primary**

| subset | group | b_model [95% CI] | b_pa | b_h | targets | questions |
|---|---|---|---|---|---|---|
| pooled | S | -0.23 [-0.77, 0.30] | 1.5583 | 1.7892 | 578 | 162 |
| pooled | P | 0.72 [0.32, 1.12] | 1.6960 | 0.9718 | 578 | 162 |
| dataset | S | 0.01 [-0.76, 0.78] | 2.1673 | 2.1569 | 521 | 105 |
| dataset | P | 1.04 [0.43, 1.65] | 2.1210 | 1.0814 | 521 | 105 |
| market | S | -0.30 [-1.20, 0.61] | 0.8243 | 1.1196 | 57 | 57 |
| market | P | -0.61 [-1.45, 0.23] | 1.3334 | 1.9430 | 57 | 57 |

**clip (0.001, 0.999), sensitivity**

| subset | group | b_model [95% CI] | b_pa | b_h | targets | questions |
|---|---|---|---|---|---|---|
| pooled | S | -0.24 [-0.77, 0.29] | 1.5251 | 1.7650 | 578 | 162 |
| pooled | P | 0.72 [0.32, 1.12] | 1.6955 | 0.9715 | 578 | 162 |
| dataset | S | 0.01 [-0.76, 0.78] | 2.1612 | 2.1530 | 521 | 105 |
| dataset | P | 1.04 [0.43, 1.65] | 2.1208 | 1.0814 | 521 | 105 |
| market | S | -0.30 [-1.19, 0.60] | 0.7791 | 1.0749 | 57 | 57 |
| market | P | -0.61 [-1.45, 0.24] | 1.3357 | 1.9442 | 57 | 57 |

Descriptive only. Pooled, the public-median fit leaves a positive model increment (the interval excludes zero); the superforecaster-median fit does not (interval includes zero). By source, only the public median on dataset targets has an interval excluding zero; market intervals (57 targets, one per question) are wide.

## 2. Superforecaster ids

`2024-07-21.ForecastBench.human_super_individual.json` has **40 distinct user_id values** (7693 rows). Fields per row: id, source, forecast, resolution_date, reasoning, direction, user_id, searches, consulted_urls. **The file has no forecast timestamp and no stage field**, so first and last forecast dates and single-stage membership cannot be computed from the data; they are reported as not available. The other local files for this round do not carry them either: the aggregate `human_super.json` (raw and processed forecast sets) and the question set `2024-07-21-human.json` have no timestamp or stage field. The word "stage" occurs in 20 reasoning texts, all ordinary usage ("group stage", "late stage", "hostage"), not a stage marker.

| user_id | forecasts | targets (file) | questions | duplicate rows | targets in frame | market targets in frame | with reasoning | with searches | first/last date | one stage only |
|---|---|---|---|---|---|---|---|---|---|---|
| SSjRQHn8XG | 4 | 4 | 4 | 0 | 4 | 4 | 100% | 50% | n/a | n/a |
| SCyupbOzJd | 63 | 63 | 21 | 0 | 40 | 10 | 90% | 16% | n/a | n/a |
| SsEu23bmu9 | 75 | 75 | 26 | 0 | 48 | 15 | 100% | 23% | n/a | n/a |
| SFXe6kW9Yt | 88 | 88 | 39 | 0 | 59 | 24 | 100% | 62% | n/a | n/a |
| S3X40UQlAj | 89 | 89 | 19 | 0 | 56 | 6 | 100% | 25% | n/a | n/a |
| SqSCtDbxAl | 94 | 94 | 24 | 0 | 56 | 11 | 99% | 6% | n/a | n/a |
| S5CrWZaPfh | 94 | 94 | 24 | 0 | 63 | 13 | 100% | 24% | n/a | n/a |
| SnOyJtNds8 | 96 | 96 | 33 | 0 | 62 | 17 | 100% | 19% | n/a | n/a |
| Si0VpEBOWf | 101 | 101 | 17 | 0 | 64 | 4 | 100% | 1% | n/a | n/a |
| ScR8KykF8V | 110 | 110 | 19 | 0 | 64 | 4 | 100% | 0% | n/a | n/a |
| SZINl91huS | 112 | 112 | 35 | 0 | 75 | 20 | 100% | 71% | n/a | n/a |
| SPxBFWGyEb | 112 | 112 | 21 | 0 | 72 | 7 | 100% | 16% | n/a | n/a |
| SXXYp0Pfba | 113 | 113 | 37 | 0 | 77 | 23 | 100% | 88% | n/a | n/a |
| S2co9AhkoU | 118 | 118 | 34 | 0 | 77 | 17 | 100% | 53% | n/a | n/a |
| Sg4x84spDg | 120 | 120 | 36 | 0 | 82 | 22 | 100% | 82% | n/a | n/a |
| SIeeNsXE1j | 123 | 123 | 19 | 0 | 66 | 2 | 100% | 28% | n/a | n/a |
| SsuHJKpbpe | 123 | 123 | 32 | 0 | 78 | 13 | 99% | 7% | n/a | n/a |
| SSPpd7YIH0 | 131 | 131 | 19 | 0 | 82 | 2 | 100% | 44% | n/a | n/a |
| S2s1t6Uzpa | 133 | 133 | 42 | 0 | 86 | 21 | 100% | 20% | n/a | n/a |
| SFKcpXzkIR | 136 | 136 | 60 | 0 | 85 | 41 | 100% | 0% | n/a | n/a |
| S2cY7Jk18R | 139 | 139 | 55 | 0 | 92 | 33 | 100% | 24% | n/a | n/a |
| Sg3FmLYbbj | 144 | 144 | 47 | 0 | 89 | 26 | 100% | 30% | n/a | n/a |
| SnBEoonCrb | 149 | 149 | 37 | 0 | 88 | 19 | 100% | 58% | n/a | n/a |
| SiIgce1WZv | 149 | 149 | 37 | 0 | 88 | 18 | 96% | 0% | n/a | n/a |
| S488gnM8HQ | 153 | 153 | 42 | 0 | 99 | 20 | 100% | 0% | n/a | n/a |
| SOca8sKBtd | 166 | 166 | 41 | 0 | 104 | 15 | 100% | 73% | n/a | n/a |
| SON6ytut03 | 182 | 182 | 56 | 0 | 117 | 32 | 100% | 4% | n/a | n/a |
| SgF5s3i4bt | 201 | 201 | 54 | 0 | 129 | 25 | 100% | 1% | n/a | n/a |
| S3bbH6xnAb | 209 | 209 | 55 | 0 | 132 | 27 | 100% | 42% | n/a | n/a |
| S7aWY2TYGI | 217 | 217 | 57 | 0 | 137 | 28 | 100% | 4% | n/a | n/a |
| SS6AZPsK20 | 232 | 232 | 85 | 0 | 152 | 52 | 100% | 0% | n/a | n/a |
| SH1oF7JCqH | 252 | 252 | 98 | 0 | 161 | 56 | 100% | 0% | n/a | n/a |
| SbZAVaBSo6 | 274 | 274 | 65 | 0 | 168 | 30 | 100% | 17% | n/a | n/a |
| SwihqZyyLo | 284 | 284 | 67 | 0 | 174 | 29 | 100% | 0% | n/a | n/a |
| SE9oSfk4nV | 298 | 298 | 60 | 0 | 169 | 21 | 100% | 6% | n/a | n/a |
| SWvnPZ5v2Q | 299 | 299 | 90 | 0 | 196 | 47 | 100% | 0% | n/a | n/a |
| SMWxJnfq3I | 386 | 386 | 86 | 0 | 238 | 30 | 100% | 23% | n/a | n/a |
| SHMLCbokK1 | 391 | 391 | 105 | 0 | 242 | 48 | 100% | 2% | n/a | n/a |
| SUpgMvejGk | 576 | 576 | 100 | 0 | 348 | 25 | 99% | 6% | n/a | n/a |
| SPqHtpfr8B | 957 | 957 | 189 | 0 | 578 | 57 | 100% | 0% | n/a | n/a |

`targets (file)` counts (source, id, resolution_date) keys as filed; market rows carry a null resolution date, so each market question is one key. `targets in frame` is after resolution mapping and the v1 exclusions (no superforecaster row is outside [0, 1]). All 40 ids are in the analysis frame.

**Does one id stand out?** Yes, on volume: **`SSjRQHn8XG` has 4 forecasts** (4 market questions, all 4 in the frame); the next smallest id has 63. At the other end `SPqHtpfr8B` forecast all 189 questions (957 rows, all 578 frame targets). No duplicate pattern: no id has more than one row per target, no reasoning text longer than 40 characters is shared between ids, and the highest share of identical forecasts between two ids is 0.82 on only 11 shared targets (S5CrWZaPfh, SiIgce1WZv), consistent with round values on the same questions rather than copied submissions. Late entry cannot be assessed (no timestamps). Whether `SSjRQHn8XG` is the id behind the paper's 39 is **not verified**: the paper's count was not checked against a definition here, and the data carry nothing that would mark an id as excluded. Nobody is dropped.

## 3. Amendment 6: the maximum constrained fold SD

The maximum fold-to-fold SD among the constrained C3/C4 weights, 0.099, is **H_P+M1 under C3** (weight on the public median: SD 0.0993, mean 0.476, range 0.320–0.563). Next is H_P+Mens under C3 (SD 0.0991). Both are below the 0.2 rule.

Confirmed for **H_S+M1**: the C3 weight on the human is 1.000000 in all five folds (SD 0). The C4 weight is 0.9999995 in all five folds (SD below 1e-6, shown as 0.000). That is the upper bound 1 to within the bounded optimizer's tolerance (xatol 1e-6), not an interior value. The same holds for H_S+Mens.

## 4. Where the +0.097 / 0.0979 superforecaster-vs-M1 log-score number appears

It is **not in the v1 locked outputs**. `docs/forecast_full_REPORT.md` has no target-level superforecaster-median-vs-M1 log-score difference. Its log-score content is §7.2 (line 406): H3 and H4 refit on row-level `G_log` for individual forecasters. There, `GRP[T.S]` 0.33314 (line 415) is a group contrast in the H3 regression, not the median vs M1. The rest is the `G_log` distribution by `EXT_a` quartile (line 533).

It is **not printed in the v2 report either**. `docs/forecast_v2_full_REPORT.md` reports only the slopes of the cross-fitted gain across variants (§6.4, line 282; Amendment 2 table, lines 336–338), not the per-variant gain.

The two figures are different quantities that happen to be close:
- **0.0979** (0.097940) is the v2 cross-fitted out-of-sample log-score gain for M1 (v2 §6.4: adding the human term to a logistic recalibration of M1). It is stored only in `data/derived/v2_full_E_boot_crossfit.pkl` (gitignored). It first appears in a report at `docs/amendment6_REPORT.md:36`, as the fold check.
- **+0.097** is the Amendment 6 raw score difference, superforecaster median alone vs M1 alone, with no fitting (−0.351 vs −0.448): `docs/amendment6_REPORT.md:144`, interval [+0.060, +0.140].
