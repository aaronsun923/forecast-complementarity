# SPEC v3 (2026-10-02). Decided after the v1 and v2 results were seen. Estimands, folds, and readings fixed before execution.

Status of everything in this specification: post-results in origin, with readings locked before computation. Nothing here refits or replaces a v1 or v2 estimate. The paper reports every v3 quantity with that label.

## Amendment 5b. Encompassing by question source

Motivation. On market questions both humans and the matched model variants saw the market freeze value; on dataset questions humans could look up the latest data point and the freeze-no-news variants could not. The information gap between humans and model is therefore smaller on market questions. Splitting the H2 encompassing test by source is the most direct check available in this round of whether the human median's increment is where the information gap is.

Estimand. The Section 4.2 encompassing regression, unchanged (logit of outcome on logit(p_a) and logit(p_h) minus logit(p_a); question-clustered SE; clip [0.01, 0.99]; superforecaster median and public median separately; benchmark (a) unchanged), fit separately on the 57 market targets and the 521 dataset targets. Report both coefficients with 95% intervals per group and per subset, the target and question counts, and the clip-bound hit counts. Sensitivity: clip [0.001, 0.999]. Note in the report that 57 market targets across their questions give a wide interval; state the number of market questions.

Locked reading.
- Dataset coefficient positive and market interval includes zero: the increment is where the information gap is. The paper's main claim is restated as "relative to a model without news, on questions where humans could retrieve newer data".
- Both positive: the increment is not fully explained by access to newer data points, since on market questions both sides shared the freeze price. This is still not evidence of judgment; the paper says so.
- Market positive and dataset interval includes zero: contrary to the information-gap account. Reported in the main text as such, not in a footnote.
- The pooled Section 4.2 numbers are not changed by this amendment.

## Amendment 5. News-augmented variants

Objects. Every claude-3-5-sonnet-20240620 scratchpad variant in the 2024-07-21 round that carries news (with news; with news and freeze values), plus the single news-carrying variant of any base model with the best mean Brier on the v1 selection set (the single-question targets no human forecast). Benchmark (a) is zero-shot and has no news variant; no pairing is forced.

Coverage gate. For each news variant: share of the 578 test targets with a non-imputed forecast. Proceed only with variants at or above 90% coverage and at or below the 5% imputed-row rule. If none qualifies, write docs/amendment5_coverage.md and stop.

Estimand. The Section 4.2 encompassing regression with the news variant as the model, on the targets both that variant and benchmark (a) cover, same clip, same clustering, both group medians. Report alongside: the news variant's selection-set Brier Q, so that it is visible whether the news variant is better or worse than the freeze-only benchmark on out-of-sample questions. Also report the paired difference of the human coefficient (news variant minus benchmark (a)) with a question-level cluster bootstrap, 2,000 draws, seed 20260906.

Locked reading.
- If the news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot narrow the information-set confound. The paper reports only that the ForecastBench news pipeline did not improve this model in this round, and does not read a positive human coefficient against the news variant as evidence of judgment.
- If the news variant's Q is not worse, and the public median's coefficient against the best news variant has an interval including zero: the public increment over the freeze-only model is consistent with retrievable news. The main claim is restated as "relative to a single model without news".
- If the news variant's Q is not worse, and the public coefficient stays positive: the increment is not absorbed by this news pipeline. The paper adds in the same sentence that the pipeline may retrieve less than a human does, so this is still not evidence of judgment.
- The superforecaster coefficient is reported but never used as identification evidence on its own, because of the group stage.
- No v1 number changes. The primary benchmark is not reselected.

## Amendment 6. Out-of-sample combination

Unit. One row per target: the superforecaster median, the public median, and the model forecasts. Row-level data are not used to fit weights.

Folds. Five folds by question, every target of a question in the same fold, the same seed and fold assignment as the v2 cross-fitted log-score gain. Weights are estimated on the training folds and frozen on the test fold.

Sources per target.
- M1: benchmark (a).
- Mnews: the best-coverage news variant with the best selection-set Q under Amendment 5's gate (name filled in after Amendment 5 runs; the selection rule is fixed here). If no variant passes the gate, Mnews is dropped and the report says so.
- Mens: the median of the 33 variants other than M1, the same object as the v2 reference curve.
- Hs, Hp: the two human medians.

Combiners, fixed list.
- C1 equal-weight linear pool: (p + q)/2.
- C2 equal-weight log pool: geometric mean of odds, converted back to probability.
- C3 linear pool with weights chosen on the training folds to minimize Brier, weights clipped to [0, 1] and summing to 1 (primary); unconstrained weights as a secondary line.
- C4 log pool with weights chosen on the training folds to minimize log score, same constraint.
No further combiners.

Systems compared, each scored on every test fold and pooled, for each human group and for both scores (log score primary, Brier beside it):
1. M1 alone
2. Mens alone
3. Mnews alone (if present)
4. human median alone
5. human + M1
6. human + Mens
7. M1 + Mens (the non-human combination baseline)
8. human + M1 + Mens (C1 and C2 only)
9. noise control: the median of 7 public forecasters drawn at random on each target (seed 20260906, one draw, plus the median across 200 draws reported as a band), combined as in rows 5 and 6. This matches the superforecaster median's typical count per target.

Intervals. Question-level cluster bootstrap of the pooled out-of-sample score difference between systems, 2,000 draws, seed 20260906, refitting weights inside each draw for C3 and C4. Also report the fold-to-fold SD of each fitted weight.

Locked reading.
- "The human median carries a deployable increment" is claimed only if human + M1 beats M1 alone AND beats M1 + Mens on the primary score, with both bootstrap intervals excluding zero. Beating M1 alone is not enough; any second forecast improves a single model.
- human + Mens versus Mens alone is the co-primary question: whether the human median adds to the ensemble. This is the decision version of the v2 reference curve.
- If the log score and Brier disagree on a claim, the paper takes no side and states the disagreement in one sentence with a pointer to the companion methods paper.
- The public and superforecaster results are read separately. A claim that holds for superforecasters and not for the public is stated as a claim about the superforecaster median under tournament and web-search conditions, not about "humans".
- If a fitted weight's fold-to-fold SD exceeds 0.2, the optimized combiners (C3, C4) are reported as descriptive only and the equal-weight rows carry the claim.
- If the 7-person public median behaves like the superforecaster median against Mens, the superforecaster exception in v2 is read as a sample-size effect, not a group effect.
- No switching rules by disagreement (DIS) are fitted. That question was H3 and is closed.

## Reporting

docs/amendment5b_REPORT.md, docs/amendment5_REPORT.md, docs/amendment6_REPORT.md. Coefficients to 2 decimals, score differences to 3, with the same conventions as the v1 and v2 reports. Each report restates the locked reading and says which branch the numbers fall into, in one sentence, before any discussion.

## Amendment 7. Per-variant per-forecaster gain (LOCKED 2026-10-08, before computation)

Status: LOCKED 2026-10-08, committed before code/amendment7.py was written or run.

Purpose: Section 3 ("Which model is the ruler") of the methods paper "Relative to what?". The v2 report gives per-variant point estimates of the per-forecaster gain over each of the 34 matched variants but no intervals. This amendment adds question-clustered intervals under both scoring rules, and the reference curve's own gain over each variant, which Amendment 2 reports only as a human-minus-reference difference. Nothing here changes any P5 number.

Reads only: the existing derived frame used by v1 H1 (33,334 forecaster-target rows, 578 targets, 162 questions; v1 Amendment 2 row exclusions applied) and the 34 matched-variant forecasts already loaded by v2common. No new download.

### Quantities

1. Per-forecaster gain over variant m, for each of the 34 variants:
   - G_B(m) = Brier(m) − Brier(human), per row, as v1 H1 defines G_a with m in place of baseline (a).
   - G_L(m) = log score(human) − log score(m), per row, probabilities clipped to [0.01, 0.99], the v1/v2 convention (v1 Amendment 3 G_log).
   - Rows where m's forecast is imputed are dropped for that variant only; report the row count per variant.
   - Mean by group (S, P), ×100 for Brier as in v1, natural units for log. 95% interval: question-level cluster bootstrap, 2,000 draws, seed 20260906, percentile.
2. Reference curve's own gain over variant m: the leave-one-out median of the other 33 variants (the v2 Amendment 2 reference object, same folds, seed, clipping and target set) against m, as the cross-fitted log-score gain and the Brier gain, with the same bootstrap. This is the "vertical difference" table's missing row: reference minus m, not human minus reference.
3. Counts: for each group and each rule, the number of variants (of 34) whose interval lies entirely above zero, entirely below zero, or includes zero.

### Reading, fixed before the run

- 34 variants are not 34 independent tests. The paper reports the curve and the counts in item 3, with the variants ordered by selection-set Q. No per-variant p-values enter the paper.
- Recorded expectation from the v2 point estimates: superforecasters positive against all 34 under Brier; public positive against about 6 and negative against about 28. Whether the sign flip for the public group survives the intervals is what the counts show; the paper reports the counts whatever they are.
- Scoring-rule check for Section 5: for each variant, whether the sign of the point estimate differs between G_B and G_L, and whether an interval excludes zero under one rule and not the other. If no variant moves, Section 5 gets one sentence; if any does, the variant is named.

### Output

- code/amendment7.py (reuses v2common and the v2 Amendment 2 reference code; no new modelling).
- docs/amendment7_REPORT.md: one table per group with 34 rows (variant, scaffold, Q, n rows, G_B mean and interval, G_L mean and interval), one table for the reference gain (34 rows, both rules), the count table, the rule-disagreement list, and the usual header (frame size, seed, clip, git commit of the spec).
- docs/amendment7_pervariant.csv with every number in the tables.
- figures/amd7_gain_curve.png: G_B and G_L against Q, both groups, with intervals; reference curve overlaid.

Reproduction check: G_B against M1 (Claude-3-5-Sonnet-20240620 zero shot with freeze values) must reproduce v1 H1 exactly (+3.38 [1.36, 5.41] S; −7.81 [−9.69, −5.92] P) before any other variant is reported. If it does not, stop and report.

### Clarification (2026-10-08, before computation)
The reproduction check is passed by the point estimates (to four decimals) and by v1 H1's own analytic clustered interval recomputed on the same frame; both reproduce exactly. The intervals reported in this amendment are the question-level cluster bootstrap as specified, for all 34 variants including M1, so that they share the resampling scheme of the Amendment 2 reference curve. The M1 row of the report carries the analytic interval in a footnote beside the bootstrap one. No estimand changes.

### Note 2 (2026-10-08, after results, descriptive addition, no estimate changes)
Item 2's log-score reference gain is the Amendment 2 cross-fitted combination gain (reference added to m). Item 1's G_L is a substitution gain (human in place of m). So that the log panel compares like with like, the reference's substitution gain, log score(reference median) − log score(m) per target under the same clip, is added with the same bootstrap and plotted beside the human G_L curve. The combination gain stays in the table as specified. The Brier panel already compares substitution with substitution.
