# SPEC v2: Human Information Beyond the Model as a Function of Benchmark Quality

Status: LOCKED 2026-09-07 on confirmation of §8. The lock takes effect at the commit that adds this file to `forecast-complementarity`, which must precede any analysis run.

## 0. Note to the implementer

Same rules as SPEC v1: [LOCKED] parameters are design decisions; disagreement is reported, not patched. Reuse the v1 data frame, keys, exclusions, and helpers exactly (Amendments 1 and 2 of v1 apply in full). Do not recompute anything v1 already computed. Work in `~/Desktop/forecast-complementarity/`.

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
| `G_m,g` | mean human gain over variant m, by group. Reported as a descriptive curve only, with the statement that it is mechanical: `G_m,g = BS_m(test) − BS_g(test)` and the second term does not vary with m |

`Q_m` is the x axis. `β` and `ε` are the y axes.

## 4. Hypotheses

Units are variants (n = 34), which nest in base models (n = 17). **[LOCKED]** All standard errors cluster by base model.

### 4.1 H6: does human information beyond the model shrink as the model improves?

```
β_m,g ~ Q_m          separately for g = S and g = P, weighted by 1 / SE(β_m,g)²
```

Core quantity: the slope on `Q_m`. The expectation is positive (worse models leave more for the human to add), pre-registered two-sided.

Descriptive extrapolation, reported without inference: the value of `Q` at which the fitted `β` reaches zero, with the interval implied by the slope's 95% CI. If the fitted line does not reach zero within the observed range of `Q`, say so and do not extrapolate beyond the range.

### 4.2 H7: does the return to extremizing depend on the model's quality?

```
ε_m,g ~ Q_m          separately by group, weighted by 1 / SE(ε_m,g)²
```

Core quantity: the slope. Two-sided, no expected direction pre-registered.

### 4.3 H8: is the human information the same information across benchmarks?

For each group, compute the per-target human-minus-model term `logit(p_h_g) − logit(p_m)` for every variant m. Report the mean pairwise correlation across variants of this term (578 targets). A high correlation means the human median disagrees with all models in the same places, i.e. the information is about the questions, not about any one model's weakness. Descriptive; no test.

**[LOCKED]** No other hypotheses. No per-forecaster analysis: per-forecaster gain differs across benchmarks only through the mechanical term.

## 5. Pilot

**[LOCKED]** Same pilot subset as v1 (30% of questions, seed 20260907). Run H6 and H7 on it. Deliver §7 for the pilot. Stop. Full run waits for the designer.

## 6. Robustness (two items only)

1. `Q_m` measured on the round's combination-question targets instead of the single-question selection set; rerun H6 and H7.
2. Exclude the two Claude-2.1 variants (imputed share above 5% in v1); rerun H6 and H7 on 32 variants.

**[LOCKED]** No other versions.

## 7. Deliverables

1. Environment.
2. Per-variant table: base model, scaffold, `Q_m`, imputed count dropped, `β_m,S`, `β_m,P` with CIs, `ε_m,S`, `ε_m,P` with CIs, `G_m,S`, `G_m,P`.
3. Figure: `β` against `Q` by group, one point per variant, both scaffolds of the same base model joined by a line, fitted slope with CI band.
4. Figure: `ε` against `Q`, same layout.
5. H6 slopes and the descriptive extrapolation.
6. H7 slopes.
7. H8 mean pairwise correlation by group.
8. The two §6 robustness items.
9. A statement of what limits the reading: 17 independent base models; all from mid-2024; the two scaffolds of one base model are not independent; `Q` is measured on a different question set from the test set.

## 8. Parameters awaiting the designer's confirmation

| Parameter | Proposed value | Location |
|---|---|---|
| Quality measure | Brier on the v1 single-question selection set | §3 |
| Clustering | by base model (17) | §4 |
| Weighting | inverse variance | §4.1, §4.2 |
| Extrapolation | descriptive only, within observed range | §4.1 |
| Pilot subset | reuse v1's | §5 |
| Robustness | combination-set Q; drop Claude-2.1 | §6 |
