# SPEC v2: Human Information Beyond the Model as a Function of Benchmark Quality

Status: LOCKED 2026-09-08, §8 parameters confirmed by the designer. The lock takes effect at the commit that adds this file to `forecast-complementarity`, which must precede any analysis run.

## 0. Note to the implementer

Same rules as SPEC v1: [LOCKED] parameters are design decisions; disagreement is reported, not patched. Reuse the v1 data frame, keys, exclusions, and helpers exactly (Amendments 1 and 2 of v1 apply in full). Do not recompute anything v1 already computed. Code and reports live in `~/Desktop/forecast-complementarity/`; data is read from `~/Desktop/forecast-study/data/` through `config.py`'s `STUDY_ROOT`, as in v1.

## 1. Objective

SPEC v1 answered whether humans carry information the single best model lacks (H2: yes, both groups) and whether that information is larger where models disagree (H3: no). It left the benchmark fixed at one model. This SPEC varies the benchmark. The 2024-07-21 round has 34 model variants in the matched information condition, spanning a wide range of quality. Treating each in turn as the benchmark gives 34 points on one curve: how much information does the human median carry beyond a model of quality Q, and does that information vanish as Q improves.

The chess study is the zero point of this curve (a benchmark that is strictly stronger; no information beyond it). This SPEC fills in the interior.

## 2. Data

- **[LOCKED]** The v1 analysis frame: round 2024-07-21, 578 resolved human targets, 162 questions, 540 forecasters, human rows with p_h in [0, 1] only.
- **[LOCKED]** Benchmarks: all 34 matched-condition variants (17 base models × two scaffolds with freeze values). The v1 eligibility rule for baseline (a) (imputed share ≤ 5%) does not apply here, because no champion is chosen; every variant is a point. For each variant, targets where its forecast is imputed are dropped for that variant only; report the count per variant.

## 3. Quantities

Per variant m:

| Symbol | Definition |
|---|---|
| `Q_m` | mean Brier of variant m on the v1 selection set (single questions, complement of human targets, imputed rows excluded). Lower is better. Measured out of sample relative to the test set |
| `β_m,g` | the v1 H2 encompassing coefficient with variant m as the model and group g's median as the human: `o ~ logit(p_m) + [logit(p_h_g) − logit(p_m)]`, question-clustered SEs, clip [0.01, 0.99]. Same code path as v1 H2 |
| `ε_m,g` | the v1 H4 `EXT` coefficient with variant m as the model, all covariates as in v1 H4, group g only. Same code path as v1 H4 |
| `G_m,g` | mean human gain over variant m, by group. Reported as a descriptive curve only. **[LOCKED]** It is close to an identity: `G_m,g = BS_m(test) − BS_g(test)`, the second term does not vary with m, and `BS_m(test)` is highly correlated with `Q_m` because both are that variant's Brier on different question sets. Any figure showing it must carry that statement in its caption, not only in this table |

`Q_m` is the x axis. `β` and `ε` are the y axes.

## 4. Hypotheses

Units are variants (n = 34), which nest in base models (n = 17). The 34 points are not independent observations: every `β_m` and `ε_m` is estimated on the same 578 targets, the same human medians, and the same outcomes, so outcome noise is shared across all 34. Clustering by base model does not remove that sharing.

Inference differs between H6 and H7 because the two stage-1 estimators differ by three orders of magnitude in cost (a logistic fit for `β`, a mixed model for `ε`; one full pass over 34 variants takes about 22 minutes, almost all of it `ε`).

- **[LOCKED]** H6: question-level cluster bootstrap. Resample the 162 questions with replacement (seed 20260908), recompute every `β_m,g` on the resampled data for all 34 variants, refit the stage-2 slope, repeat 2,000 times, report the 2.5 and 97.5 percentiles. This propagates the shared outcome noise, which clustering at stage 2 cannot.
- **[LOCKED]** H7: stage-2 wild cluster bootstrap over the 17 base models (Rademacher weights, 2,000 draws, seed 20260908), applied to the 34 precomputed `ε_m,g` points. Regenerating `ε` inside each draw would take about 30 days and is not done. State in the H7 table that its interval conditions on the stage-1 estimates and is therefore narrower than H6's.
- The analytic slope with standard errors clustered by base model is reported alongside both, labeled as the narrowest and least appropriate interval; 17 clusters understate uncertainty.

**[LOCKED]** `Q_m` is held fixed across bootstrap draws. It is measured on the selection set, which contains no test targets and is not resampled.

### 4.1 H6: does human information beyond the model shrink as the model improves?

```
β_m,g ~ Q_m          separately for g = S and g = P, weighted by 1 / SE(β_m,g)²
```

Core quantity: the slope on `Q_m`. The expectation is positive (worse models leave more for the human to add), pre-registered two-sided.

Descriptive extrapolation, reported without inference: the value of `Q` at which the fitted `β` reaches zero. **[LOCKED]** Compute the zero crossing within each bootstrap draw and report the 2.5 and 97.5 percentiles across draws, so the interval comes from the same resampling as the slope. If the fitted line does not reach zero within the observed range of `Q`, say so and do not extrapolate beyond the range. Report the share of draws in which the crossing falls outside the observed range.

### 4.2 H7: does the return to extremizing depend on the model's quality?

```
ε_m,g ~ Q_m          separately by group, weighted by 1 / SE(ε_m,g)²
```

Core quantity: the slope. Two-sided, no expected direction pre-registered.

### 4.3 H8: is the human information the same information across benchmarks?

For each group, compute the per-target human-minus-model term `logit(p_h_g) − logit(p_m)` for every variant m. Report the mean pairwise correlation across variants of this term (578 targets). This correlation is mechanically inflated because every term shares `logit(p_h_g)`. **[LOCKED]** Report next to it the reference quantity: the mean pairwise correlation across variants of `logit(p_m)` itself, and the standard deviation of `logit(p_h_g)` for each group.

**[LOCKED]** Report these numbers and draw no conclusion from them. A preliminary calculation gives about 0.77 for superforecasters, 0.34 for the public, against 0.59 for the models alone. The two groups straddle the reference in opposite directions, which is what a shared-component artifact looks like rather than a difference in where the groups disagree with models: the statistic mixes the variance of the human median (which differs sharply between groups) with the models' mutual correlation. H8 is a reported quantity, not evidence for or against anything.

**[LOCKED]** No other hypotheses. No per-forecaster analysis: per-forecaster gain differs across benchmarks only through the mechanical term.

## 5. Pilot

**[LOCKED]** Same pilot subset as v1 (30% of questions, seed 20260907). Run H6 and H7 on it. Deliver §7 for the pilot. Stop. Full run waits for the designer.

## 6. Robustness (five items only)

1. `Q_m` measured on the round's combination-question targets instead of the single-question selection set; rerun H6 and H7.
2. Exclude both Claude-2.1 variants and rerun H6 and H7 on 32 variants. The exclusion is at the base-model level: only the scratchpad variant exceeds the v1 5% imputed threshold (about 5.05%); the zero-shot variant is at 0% and was eligible in v1. Both are dropped so the pair is treated consistently.
3. Leverage. `Q_m` is tightly clustered (24 of 34 variants between 0.176 and 0.211) with one far outlier (GPT-3.5-Turbo zero shot at about 0.397, 0.11 clear of the next worst, and not stabilized by its scaffold partner). Report leverage and Cook's distance for every point, and rerun H6 and H7 with the highest-`Q` variant excluded. If the slope's sign depends on that one point, the curve is reported as driven by a single variant.
4. A scale-free y for H6. `β_m` is not directly comparable across variants: the variance of the human-minus-model term grows as the model worsens, and the coefficient's scale moves with it, so the curve could be tracing variance rather than information. Replace `β_m,g` with the out-of-sample improvement in mean log score from adding the human term to the model, cross-fitted in 5 folds by question (seed 20260908), and rerun H6 with the same bootstrap. This is the heaviest computation in the SPEC (2,000 draws × 34 variants × 2 groups × 5 folds of a small logistic fit). If it exceeds one hour, stop and report rather than reducing the draws. The H6 bootstrap itself is about 45 minutes on measured per-fit times and is also subject to the one-hour tripwire. The H6 conclusion stands only if the two curves agree in sign; if they disagree, report that the `β` curve is not interpretable as information.
5. H7 under the log score. v1 found the `EXT` coefficient positive under Brier and negative under the log score. Rerun H7 with the v1 §7.2 log-score gain as the dependent variable of the per-variant `EXT` fits. Interpret only the part of the two H7 curves where the signs agree.

**[LOCKED]** No other versions.

## 7. Deliverables

1. Environment.
2. Per-variant table: base model, scaffold, `Q_m`, imputed count dropped, `β_m,S`, `β_m,P` with CIs, `ε_m,S`, `ε_m,P` with CIs, `G_m,S`, `G_m,P`.
3. Figure: `β` against `Q` by group, one point per variant, both scaffolds of the same base model joined by a line, fitted slope with CI band.
4. Figure: `ε` against `Q`, same layout. Both figures mark the points flagged by the §6 leverage check.
   - **[LOCKED]** Every reported quantity is computed on that variant's own retained targets. Twenty-eight variants keep all 578; six lose imputed targets (worst case 545). Report the target count next to every `β` and `ε`, and note that the y values are not computed on identical target sets across the x axis. No reweighting is applied for this.
5. H6 slopes and the descriptive extrapolation.
6. H7 slopes.
7. H8 mean pairwise correlation by group, reported next to the reference quantity (mean pairwise correlation of `logit(p_m)` across variants).
8. The five §6 robustness items.
9. A statement of what limits the reading: 17 independent base models; all from mid-2024; the two scaffolds of one base model are not independent; `Q` is measured on a different question set from the test set.

## 8. Parameters awaiting the designer's confirmation

| Parameter | Proposed value | Location |
|---|---|---|
| Quality measure | Brier on the v1 single-question selection set | §3 |
| Primary inference | H6 question-level cluster bootstrap; H7 stage-2 wild cluster bootstrap over base models; both 2,000 draws, seed 20260908; analytic SE reported alongside | §4 |
| Weighting | inverse variance | §4.1, §4.2 |
| Extrapolation | descriptive only, within observed range | §4.1 |
| Pilot subset | reuse v1's | §5 |
| Robustness | combination-set Q; drop Claude-2.1; leverage and drop-highest-Q; scale-free log-score y for H6; log-score H7 | §6 |

---

## Amendment 1 (2026-09-08, after pilot, before full run)

Trigger: the SPEC v2 pilot (§5; 49 questions, 171 targets, 34 variants) ran clean and returned H6 slopes in the pre-registered direction for both groups, with neither distinguishable from zero under the primary bootstrap. Two problems in the inference and reporting apparatus surfaced, and one point was found to dominate the x axis. The rulings below change **inference and reporting only. No hypothesis, band, or quantity is redefined.**

**1. Leverage rule. [LOCKED]**

A stage-2 point is flagged if `leverage > 2p/n` **or** `Cook's distance > 4/n`, where `p` is the number of stage-2 parameters and `n` the number of variants in that fit. The rule is applied mechanically and is fixed here, before the full run, so it is not chosen after seeing which point it catches. At `p = 2`, `n = 34` both thresholds equal `0.1176`.

The §6 item 3 refit on unflagged points only is a **co-primary table for H6 and H7**. It is reported immediately after the all-points table for each hypothesis, not at the end of the report with the other robustness items.

**An H6 or H7 conclusion stands only if the slope keeps its sign with flagged points removed.** If the sign does not survive, the result is reported as driven by extreme points and **no directional claim is made**.

Pilot motivation, recorded so the rule's origin is auditable. `Q_m` is not merely skewed. Thirty-two of the 34 variants sit in a narrow band, `Q` from 0.1616 to 0.2642 (width 0.103), with two isolated points at the right edge: 0.2841, then 0.3974 a further 0.113 clear of it. In the pilot's four stage-2 fits the single variant `GPT-3.5-Turbo-0125 (zero shot with freeze values)` at `Q = 0.3974` carried a leverage of 0.605 to 0.690 — that is, `h_ii` of roughly two thirds on the 0-to-1 scale, and 30% to 35% of the total leverage, which sums to `p = 2` — and reached a Cook's distance of **3.5693** in the public `β` fit, far past any conventional threshold. The pilot used a looser leverage screen (`3 × mean leverage` = 0.1765); the rule locked above is the more inclusive one and supersedes it.

**2. H7 inference. [LOCKED]**

The stage-2 wild cluster bootstrap specified in §4 **conditions on the stage-1 `ε` estimates and is not a valid interval for H7.** It is replaced.

Build a fast inner-loop estimator for `ε`: OLS with forecaster fixed effects and question-clustered standard errors. This is the estimator SPEC v1 §5 and v1 Amendment 1 D.1 already name as the sanctioned fallback for H3 and H4, so it is not a new specification.

Validate it against the v1 mixed-model point estimates **across all 34 variants**, and report the maximum absolute difference in the coefficient and in its standard error.

Then run **the same question-level cluster bootstrap as H6**: resample the questions with replacement, recompute every `ε_m,g` on the resampled data for all 34 variants, refit the stage-2 slope, 2,000 draws, seed 20260908.

If the validation shows a material discrepancy, **or** the runtime exceeds one hour, **stop and report**. In that case H7 is demoted to descriptive, reported with **no interval**, and the H7 figure carries that statement.

**3. Reporting. [LOCKED]**

Every `ε` table carries a **per-variant column** recording whether that variant's mixed-model fit raised the optimiser boundary warning. An aggregate count is not sufficient. The pilot reported these in aggregate only; that is corrected here.

All other clauses unchanged.

---

## Amendment 2 (2026-09-08, after results, diagnostics only, no estimate changes)

Trigger: the full run returned H6 curves that are positive across the whole observed range of `Q` and rise as the model worsens. The cross-fitted out-of-sample log-score gain of §6 item 4 is positive on **all 34 variants for both groups** (superforecasters, per-variant gain 0.0731 to 0.2978, median 0.1713; public, 0.0087 to 0.1857, median 0.0750), with slopes on `Q` of +1.0957 [0.8167, 1.4223] and +1.0145 [0.7050, 1.3193]. That pattern is what the reference curve below is designed to interrogate.

**Reference curve. [LOCKED]**

The H6 curves show that adding a human term improves on a model, and that the improvement grows as the model worsens. **That slope is close to mechanical: any predictor that is not pure noise improves more on a worse model.** To establish that what the human adds is not simply what any additional forecaster-like source would add, compute a reference curve.

For each variant `m`, replace the human median with **the median forecast of the other 33 variants on that target**, and compute the same two y quantities against the same `Q_m`:

1. the encompassing coefficient (the §3 `β` estimator), and
2. the cross-fitted out-of-sample log-score gain of §6 item 4,

using the **identical folds, seed, clipping, and target sets** as the corresponding human quantities. Nothing else about either estimator changes.

Report both reference curves **on the same figures as the human curves**.

Report the **vertical difference between the human and reference curves** at the minimum, median, and maximum observed `Q`, and at each of those three points report the **question-level cluster bootstrap interval for that difference**, 2,000 draws, seed 20260908 — the same bootstrap as H6, with the difference computed inside each draw so the interval reflects the paired structure.

**The reading is locked in advance.** The claim that the human carries information the models do not is supported **only where the human curve lies above the reference curve**. Where it does not, the section reports that the human's contribution at that benchmark quality **is not distinguishable from what another model-like source contributes**.

This amendment adds a diagnostic. **No pre-registered estimate is refit or changed**; H6, H7, H8 and the five §6 robustness items stand exactly as reported.

All other clauses unchanged.
