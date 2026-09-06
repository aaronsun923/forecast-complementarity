# SPEC v1: Human Deviation from Model Forecasts and Its Return (Forecasting Study)

Status: LOCKED 2026-09-06, §11 parameters confirmed by the designer. The lock takes effect at the first commit of the public repository `forecast-complementarity`, which must precede any analysis run.

## 0. Note to the implementer

Every parameter marked **[LOCKED]** is a research-design decision, not an implementation detail. Do not change it. If you believe one is wrong, stop and state your reasoning in the report; do not change it and keep running. Everything else (code structure, storage, parallelism) is your call.

This is the second study in a line that began with the chess study in `chess-behavioral-lab` (Paper 4, SPEC v3). It reuses that study's discipline: pilot before full run, explicit sign tests, pre-specified models only, null results reported as they come, faults disclosed. It does not reuse its code. Work in `~/Desktop/forecast-study/`. Do not read or modify the chess directories.

---

## 1. Objective

The chess study found that human deviations from a strictly stronger engine have a direction (toward sharper positions) and that the direction is not repaid: sharper deviations lose more, and the opponent's error beyond what difficulty explains does not rise with sharpness. The paper's closing question was whether the same kind of deviation earns a return where the benchmark itself can err.

This study answers that question in a domain where the benchmark is fallible. In ForecastBench, human forecasters and language models forecast the same questions, and the questions resolve. The models are wrong often enough for human judgment to have room to add value.

Three questions, in order:

1. On average, does a human forecast beat the model forecast on the same question? (H1)
2. Does the human forecast carry information about the outcome that the model forecast does not? (H2)
3. Under what conditions, and in which direction of deviation, is the human's return largest? (H3, H4)

Plus one bridge to the individual-difference line: is the return a stable property of the forecaster? (H5)

---

## 2. Data

### 2.1 Source

- ForecastBench (Karger et al., ICLR 2025). Human forecasts: `forecastbench-datasets` GitHub repository, commit `68932db171f5e13349d9bda0dd9f96fcf6e227e2`. Model forecasts: the two tarballs published at forecastbench.org/datasets.html, snapshot recorded in `data/PROVENANCE.md` with SHA-256 and ETag.
- **[LOCKED]** Only the snapshot recorded in `data/PROVENANCE.md` is used. No re-download during the study.
- License: CC BY-SA 4.0. Any derived dataset we publish inherits BY-SA. Code is ours. No use of the ForecastBench name as branding.

### 2.2 The analysis round

- **[LOCKED]** Round `2024-07-21`, the only round with individual-level human forecasts. 40 superforecasters (ids prefixed S) and 500 public forecasters (ids prefixed P), 189 questions.
- **[LOCKED]** Unit of analysis: one forecaster × one target, where a target is a (question, resolution date) pair as defined by ForecastBench. Question ids are not unique across sources; the key is (source, id, resolution date).
- **[LOCKED]** Only targets with `resolved == true` and an outcome in {0, 1}. Unresolved rows carry a live market value in the same field and are excluded. Expected: 578 targets across 162 questions (521 dataset, 57 market). Report the actual counts.
- **[LOCKED]** Targets nest in questions. Outcomes of the same question at different resolution dates are highly correlated and often identical, so the effective number of independent clusters is the number of questions (about 162), not the number of targets. Every clustered standard error in this SPEC clusters by question, and every mixed model carries a question-level random intercept in addition to the target-level one.
- Report per-forecaster coverage: number of resolved targets forecast, min, median, max, by group.

### 2.3 Model forecasts on the same targets

- All models in round 2024-07-21 that forecast the full LLM question set. Expected: 139 models on an identical target set. Report the count and confirm that every human target is covered by every model; list any gaps.
- **[LOCKED]** Information condition. ForecastBench ran model variants with and without access to the crowd/market value on market questions. The human survey's information condition must be identified from the paper (Appendix B and I) and the baseline model set restricted to the variant that matches it. State the condition and the resulting model count in the report.

---

## 3. Quantities per forecaster × target row

All probabilities are for the event resolving to 1.

| Symbol | Definition |
|---|---|
| `p_h` | the human's forecast |
| `p_a` | baseline (a): forecast of the single best model, see §4 |
| `p_b` | baseline (b): median forecast across all models in the matched information condition |
| `o` | outcome, 0 or 1 |
| `BS(p)` | (p − o)² |
| `G_a` | BS(p_a) − BS(p_h). Positive = the human beat baseline (a) on this target |
| `G_b` | BS(p_b) − BS(p_h) |
| `D_a` | p_h − p_a, signed deviation from baseline (a) |
| `absD_a` | \|D_a\| |
| `EXT_a` | \|p_h − 0.5\| − \|p_a − 0.5\|. Positive = the human is more extreme than the model. This is the forecasting analog of chess sharpness |
| `DIS` | standard deviation of forecasts across all matched-condition models on the target. Cross-model disagreement, the analog of engine line spread |
| `CONF_a` | \|p_a − 0.5\|, the baseline model's own confidence |
| `HZ` | forecast horizon in days (resolution date minus forecast date) |
| `MKT` | 1 if market question, 0 if dataset question |
| `SRC` | question source (Metaculus, INFER, Manifold, FRED, ACLED, etc.), categorical |
| `GRP` | S or P |

- **[LOCKED]** Brier score in raw units (0 to 1). Tables report values × 100 for readability and say so.
- **[LOCKED]** No winsorization: Brier is bounded.
- **[LOCKED]** Explicit sign tests: assert `G_a` is positive on 20 hand-listed rows where the human is visibly closer to the outcome than the model, and negative on 20 where the model is closer. Assert `EXT_a` is positive on 10 rows where the human's forecast is visibly more extreme. List the rows in the report.

---

## 4. Baseline selection

- **[LOCKED]** Baseline (a) = the single model with the best mean Brier score on the **selection set**, defined as the round's resolved LLM targets **minus every target that any human forecast** (the complement of the human subset), within the information condition matched to the human survey, as computed by us from the processed forecast sets. Not taken from the leaderboard page, which may have been recomputed since. Report the selection set size, the model's name, its Brier on the selection set, and the runner-up's, so the choice is auditable. Ties broken toward the model with more resolved targets.
- **[LOCKED]** Baseline (b) = the median across all matched-condition models on each target.
- Baseline (a) is the primary baseline for every hypothesis. Baseline (b) appears only in §7 robustness.
- Selecting on the complement and testing on the human subset keeps the two sets disjoint, so the champion is chosen out of sample. Selecting on the full set would not: the human targets are inside it, and a model chosen partly on those outcomes would be favored on them, pushing `G_a` down toward the no-gain conclusion. Report that the intersection of selection set and test set is empty.

---

## 5. Hypotheses and models (all pre-specified)

Random effects: crossed random intercepts for forecaster and question, with target nested in question: `(1 | forecaster) + (1 | question) + (1 | question:target)`. If the fit is degenerate or does not converge, fall back to question-clustered OLS with forecaster fixed effects and say so in every affected table. Standardize continuous predictors; report standardized coefficients with 95% CIs.

### 5.1 H1: does the human beat the model on average?

```
G_a ~ GRP + (1 | forecaster) + (1 | question) + (1 | question:target)
```

Core quantities: the group-specific means of `G_a` with 95% CIs, for S and for P. This largely restates the published leaderboard and is reported as the baseline fact, not as the contribution.

### 5.2 H2: does the human forecast carry information the model lacks?

Forecast-encompassing test, target level. Because the outcome is fixed within a target, aggregate humans first:

- `p_h_S` = median human forecast among superforecasters on the target; `p_h_P` = median among public forecasters.

```
o ~ logit(p_a) + [logit(p_h_S) − logit(p_a)]        (logistic, question-clustered SEs)
o ~ logit(p_a) + [logit(p_h_P) − logit(p_a)]
```

Core quantity: the coefficient on the human-minus-model term. Positive and bounded away from zero = the human aggregate carries outcome information the model does not encompass. Report the two groups separately. Do not pool them.

**[LOCKED]** Clip probabilities to [0.01, 0.99] before the logit. Report how many values were clipped.

### 5.3 H3: where does the return live?

```
G_a ~ DIS_z + CONF_a_z + HZ_z + MKT + GRP
      + (1 | forecaster) + (1 | question) + (1 | question:target)
```

Core quantity: the coefficient on `DIS_z`. The complementarity claim from the chess paper's conclusion predicts that the human's return rises where the models disagree, i.e. where the benchmark is most fallible. A positive coefficient supports it. `CONF_a_z`, `HZ_z`, `MKT` are controls and are reported without interpretation beyond sign.

### 5.4 H4: does the direction of deviation pay?

```
G_a ~ EXT_a_z + absD_a_z + DIS_z + CONF_a_z + HZ_z + MKT + GRP
      + (1 | forecaster) + (1 | question) + (1 | question:target)
```

Core quantity: the coefficient on `EXT_a_z`, holding the size of the deviation fixed. This is the direct analog of the chess H2 (sharpness coefficient on net gain). In chess it was negative. Here the prediction is two-sided and pre-registered as such: extremizing relative to the model may pay (the model is underconfident) or cost (the human is overconfident). Report the sign and interpret only the sign.

**[LOCKED]** One interaction only: `EXT_a_z : DIS_z`. Does extremizing pay more where the models disagree? No other interactions.

### 5.5 H5: is the return a stable property of the forecaster?

- **[LOCKED]** Demean first, leave-one-out: replace `G_a` with `G_a` minus the mean of `G_a` across all other forecasters on that target (the forecaster's own row excluded). Including the own row would shrink the correlation toward zero, by about 2.5% per row in the S group. Public forecasters answered different subsets of targets, and which targets a forecaster covered is not random, so target difficulty would otherwise leak into both half-means through coverage and inflate the correlation. Demeaning removes the target component; the quantity keeps its meaning.
- Split each forecaster's resolved targets into two halves by a fixed random assignment of targets (seed 20260906, the same split for every forecaster).
- Compute each forecaster's mean leave-one-out demeaned `G_a` in each half.
- Core quantity: the correlation across forecasters between the two half-means, reported separately for S and P, with bootstrap 95% CIs (resample forecasters, 2,000 draws).
- Also report the variance component of the forecaster random intercept from the H3 model as a share of total variance.

A positive split-half correlation means "who has complementarity" is a stable individual attribute. That is the quantity the individual-difference line needs.

**[LOCKED]** No further subgroup analysis. These five hypotheses are the analysis.

---

## 6. Pilot

- **[LOCKED]** Pilot on a random 30% of resolved targets, seed 20260907, all forecasters. Record the target list.
- Run everything in §3 through §5 on the pilot. Deliver §9 for the pilot. Stop. Full run waits for the designer's confirmation that the pipeline is correct and signs are sensible.

---

## 7. Robustness (three items only)

1. Baseline (b) in place of baseline (a): rerun H1, H3, H4 with `G_b`, `EXT_b`, `absD_b`, `CONF_b`. Purpose: does the conclusion depend on which single model is the benchmark.
2. Log score in place of Brier: `G_log = log(p_h_o) − log(p_a_o)` where `p_o` is the probability assigned to the realized outcome, probabilities clipped to [0.01, 0.99]. Rerun H3 and H4.
3. Dataset questions only (drop the 57 market targets): rerun H3 and H4. Purpose: market questions may carry a crowd signal that both humans and models saw.

**[LOCKED]** No other versions.

---

## 8. Compute

- Rows: about 540 forecasters × up to 578 targets, at most ~310,000 rows. No engine, no API calls. Minutes on a laptop. If anything takes more than an hour, something is wrong; stop and report.
- Resumability is not needed. Reproducibility is: one script, one seed file, deterministic output.

---

## 9. Deliverables

1. Environment and versions.
2. Data coverage: forecasters by group; resolved targets; per-forecaster coverage distribution; model count in the matched information condition; any human target lacking a model forecast; clip counts.
3. Baseline (a): the selection set size, the chosen model, its selection-set Brier, the runner-up, and confirmation that the intersection of selection set and test set is empty.
4. Sign tests listed as in §3.
5. Distributions of `G_a`, `D_a`, `EXT_a`, `DIS` (histogram plus quantiles), by group.
   - `EXT_a` has a known blind spot: a human forecast that crosses 0.5 to the model's opposite side can register as "more extreme" without being an extremization of the model's view. Report the share of rows where `p_h` and `p_a` lie on opposite sides of 0.5, and plot the `EXT_a` distribution separately for crossing and non-crossing rows. If the share is material, the H4 interpretation must say so.
6. H1 group means with CIs.
7. H2 encompassing coefficients, both groups.
8. H3 table.
9. H4 table including the one interaction.
10. H5 split-half correlations with bootstrap CIs, and the forecaster variance share.
11. The three §7 robustness items.
12. A short statement of what in the data could break the interpretation: information the humans had that models did not or vice versa, the single-round limitation, and the small number of questions relative to forecasters, with the implication that question-level moderators (H3, H4) are estimated on about 162 independent clusters and the CIs should be read accordingly.

## 10. Stop rule

Stop after the pilot deliverables. Stop again after the full-run deliverables. The designer decides what, if anything, follows.

## 11. Parameters confirmed by the designer (2026-09-06, all [LOCKED])

| Parameter | Value | Location |
|---|---|---|
| Primary baseline | single best model on the complement of the human targets, matched information condition | §4 |
| Secondary baseline | median across matched-condition models | §4, §7 |
| Human aggregate for H2 | median within group | §5.2 |
| Probability clip | [0.01, 0.99] | §5.2, §7 |
| Extremization measure | \|p_h − 0.5\| − \|p_a − 0.5\| | §3 |
| Disagreement measure | SD of model forecasts on the target | §3 |
| H4 interaction | EXT × DIS only | §5.4 |
| Split-half seed | 20260906 | §5.5 |
| Pilot fraction and seed | 30%, 20260907 | §6 |
| Bootstrap draws | 2,000 | §5.5 |

---

## Amendment 1 (2026-09-06, after lock, before execution)

Trigger: the implementer's feasibility audit found four silent-failure hazards, six internal inconsistencies, and one disputed [LOCKED] definition. The rulings below are design decisions by the designer. No analysis has run.

**A. Join and key handling**

1. Normalize `resolution_date` to a calendar date (first 10 characters) before any join. Human market rows carry a null `resolution_date`; fill it from the resolution set by (source, id). The 4 market questions with no resolution row are unresolved and drop as §2.2 already requires; report the count.
2. Combination questions are excluded from every set in this study (see B.1), so no combination key is needed.
3. **[LOCKED]** `imputed == true` rows are excluded everywhere. In model ranking (§4) and in `DIS`, a model contributes only its non-imputed forecasts. In the test set, a forecaster × target row is dropped if baseline (a) is imputed on that target; report the count. A model with more than 5% imputed rows on the selection set is ineligible to be baseline (a); report the imputed share of every matched model.

**B. Baseline selection**

1. **[LOCKED]** The selection set is restricted to **single questions** (not combination questions): resolved single-question targets in the matched condition minus every human target. Expected 930 targets across 241 questions. Reason: 86% of the unrestricted set is combination questions, a task absent from the test set; the champion should be chosen on the task it is tested on. Report, as a diagnostic only, which model would have won on the unrestricted set.
2. Tie-break replaced: ties on the selection set are broken toward the lower Brier on the round's combination-question targets. Report if a tie occurs.
3. Information condition, ruling on §2.3: the human survey saw freeze values on both question families and received no supplied news (paper Appendix D.2, Figures 2 and 3, and §5.1; not Appendices B and I as the spec stated). Matched condition = freeze values, no news. **Both scaffolds qualify**: 17 base models × {zero shot with freeze values, scratchpad with freeze values} = 34 model variants. Baseline (a) is the best of the 34. Baseline (b) is the median across the 34.

**C. Disagreement measure**

1. **[LOCKED]** `DIS` is redefined to exclude scaffold sensitivity: for each target, compute the SD of forecasts across the 17 base models within each scaffold separately, then average the two SDs. The audit's point stands: a single model whose two scaffolds disagree is not benchmark fallibility. Report the SD across all 34 variants as a diagnostic alongside.

**D. Model specification fixes**

1. §5 fallback for H1: question-clustered OLS **without** forecaster fixed effects (GRP is constant within forecaster and would not be identified). Fallback for H3 and H4 keeps forecaster fixed effects; there GRP is absorbed and software will drop it silently, which is correct, so every such table carries the note "GRP absorbed by forecaster fixed effects, not separately reported".
2. `HZ` enters as log(days), standardized. Note in the H3 and H4 tables that `HZ` and `MKT` are partly redundant because market and dataset horizons come from different distributions.
3. H4 tables carry a note: `EXT_a = |p_h − 0.5| − CONF_a` by construction, so the `EXT_a` coefficient is the effect of the human's extremity at fixed model confidence and fixed deviation size. Nothing else changes.
4. `SRC` is descriptive only (coverage tables); it enters no model. §3 is not edited; this line governs.
5. §5.5 leave-one-out mean is **pooled** across both groups (all other forecasters on the target regardless of group). The own-row share is about 1.8% pooled; the 2.5% figure in §5.5 was approximate and is superseded.

**E. Pilot**

1. **[LOCKED]** The pilot samples 30% of **questions** (not targets), seed 20260907, and carries all their targets, so nesting is preserved. H5 is excluded from the pilot and runs on the full sample only; a 30% pilot leaves too few targets per forecaster for a split-half.

**F. Corrections of stated figures**

1. §2.3 "139 models" is the all-condition count including 9 non-LLM baselines; LLM variants are 130; matched-condition variants are 34.
2. §8 row count: about 33,500 forecaster × target rows (S about 4,800, P about 28,700), not 310,000. The one-hour tripwire stands.
3. The paper reports 39 superforecasters; the data has 40 distinct S ids. Footnote this in the report.
4. Report per-target S forecaster counts (min 3). The H2 superforecaster median is a median of as few as 3 forecasts on some targets; the H2 S-group coefficient must be interpreted with that thinness stated next to it.

All other clauses unchanged.
