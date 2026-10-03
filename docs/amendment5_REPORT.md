# SPEC v3 Amendment 5: news-augmented variants

Post-results in origin; reading locked in specs/forecast_spec_v3.md (commit `751e0fb`) before computation. No v1 number changes; the primary benchmark is not reselected.

## Result against the locked reading

Benchmark (a), `Claude-3-5-Sonnet-20240620 (zero shot with freeze values)`, has selection-set Q = 0.1616. Best news variant passing the gate by selection-set Q: `Claude-3-5-Sonnet-20240620 (superforecaster with news 1)` (Q = 0.1737). **Branch 1: news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot narrow the information-set confound.**

- `Sonnet 3.5 (scratchpad with news)` (Q = 0.1794): branch 1, news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot narrow the information-set confound.
- `Sonnet 3.5 (scratchpad with news with freeze values)` (Q = 0.1763): branch 1, news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot narrow the information-set confound.
- `Sonnet 3.5 (scratchpad with SECOND news)` (Q = 0.2136): branch 1, news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot narrow the information-set confound.

## Locked reading (restated from SPEC v3)

- If the news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot narrow the information-set confound. The paper reports only that the ForecastBench news pipeline did not improve this model in this round, and does not read a positive human coefficient against the news variant as evidence of judgment.
- If the news variant's Q is not worse, and the public median's coefficient against the best news variant has an interval including zero: the public increment over the freeze-only model is consistent with retrievable news. The main claim is restated as "relative to a single model without news".
- If the news variant's Q is not worse, and the public coefficient stays positive: the increment is not absorbed by this news pipeline. The paper adds in the same sentence that the pipeline may retrieve less than a human does, so this is still not evidence of judgment.
- The superforecaster coefficient is reported but never used as identification evidence on its own, because of the group stage.
- No v1 number changes. The primary benchmark is not reselected.

## Objects and coverage gate

News scaffolds in the round: scratchpad with SECOND news, scratchpad with news, scratchpad with news with freeze values, superforecaster with news 1, superforecaster with news 2, superforecaster with news 3. Selection set: the v1 selection set (930 single targets no human forecast), Brier on non-imputed rows, as in v1 §4. Coverage: share of the 578 test targets with a non-imputed forecast; gate ≥ 90%. Imputed rule: v1 A.3 selection-set imputed share ≤ 5%.

| model | role | Q_sel | n_sel_scored | sel_imputed_share | coverage | test_targets_nonimputed | test_imputed | passes |
|---|---|---|---|---|---|---|---|---|
| Claude-3-5-Sonnet-20240620 (scratchpad with news) | Sonnet scratchpad with news (spec-listed) | 0.1794 | 930 | 0.0% | 100.0% | 578 | 0 | yes |
| Claude-3-5-Sonnet-20240620 (scratchpad with news with freeze values) | Sonnet scratchpad with news (spec-listed) | 0.1763 | 930 | 0.0% | 100.0% | 578 | 0 | yes |
| Claude-3-5-Sonnet-20240620 (scratchpad with SECOND news) | Sonnet scratchpad with news (not in spec parenthetical; flagged) | 0.2136 | 929 | 0.1% | 100.0% | 578 | 0 | yes |
| Claude-3-5-Sonnet-20240620 (superforecaster with news 1) | best selection-set Q among news variants of any base model | 0.1737 | 930 | 0.0% | 100.0% | 578 | 0 | yes |

Benchmark (a) for comparison: Q = 0.1616, selection-set imputed share 0.0%.

**Interpretation flag.** The spec names "every claude-3-5-sonnet-20240620 scratchpad variant that carries news (with news; with news and freeze values)". The round also contains `Claude-3-5-Sonnet-20240620 (scratchpad with SECOND news)`, a Sonnet scratchpad variant that carries news but is not in the parenthetical. It is run and shown but labelled; it does not enter the branch statement unless it is the best passing variant by Q.

**What "superforecaster with news 1" is.** In the ForecastBench code (forecastbench-code, `src/helpers/llm_crowd_prompts.py` at the parent of commit 6566923, `SUPERFORECASTER_*_PROMPT_1`) it is a 15-step structured prompt ("You are an expert superforecaster" framing; base rate, reasons up and down, odds, conditional statements, final probability) filled with the question, background, resolution criteria, dates, and `retrieved_info` (titles and summaries of retrieved news articles); the dataset version also carries the latest data value at freeze, and the current `forecast_variants.py` declares `market_prompt_uses_freeze_values=False` for this variant, so on market questions it did not see the market freeze value that benchmark (a) saw. The template has no field for any ForecastBench human (superforecaster or public) forecast. Not verified: the code that actually ran this variant in the 2024-07-21 round is not in the local snapshot, so the template-to-variant mapping rests on the names and the variant declaration, not on the run code.

Selection-set Q for every news variant (all base models), for reference:

| model | Q_sel | n_sel_scored | sel_imputed_share | coverage |
|---|---|---|---|---|
| Claude-3-5-Sonnet-20240620 (superforecaster with news 1) | 0.1737 | 930 | 0.0% | 100.0% |
| Claude-3-5-Sonnet-20240620 (scratchpad with news with freeze values) | 0.1763 | 930 | 0.0% | 100.0% |
| Claude-3-5-Sonnet-20240620 (scratchpad with news) | 0.1794 | 930 | 0.0% | 100.0% |
| Claude-3-5-Sonnet-20240620 (superforecaster with news 3) | 0.1854 | 882 | 5.2% | 93.8% |
| Qwen1.5-110B-Chat (scratchpad with news with freeze values) | 0.1921 | 930 | 0.0% | 100.0% |
| Claude-3-Opus-20240229 (superforecaster with news 1) | 0.1925 | 930 | 0.0% | 99.8% |
| Gemini-1.5-Pro (scratchpad with news with freeze values) | 0.1934 | 929 | 0.1% | 99.8% |
| Qwen1.5-110B-Chat (scratchpad with news) | 0.1939 | 930 | 0.0% | 100.0% |
| Gemini-1.5-Pro (scratchpad with news) | 0.1950 | 928 | 0.2% | 100.0% |
| GPT-4-Turbo-2024-04-09 (scratchpad with news with freeze values) | 0.1961 | 930 | 0.0% | 99.8% |
| GPT-4-Turbo-2024-04-09 (superforecaster with news 3) | 0.1962 | 676 | 27.3% | 77.3% |
| GPT-4o (scratchpad with news with freeze values) | 0.1979 | 930 | 0.0% | 100.0% |
| GPT-4-Turbo-2024-04-09 (scratchpad with news) | 0.1988 | 930 | 0.0% | 100.0% |
| GPT-4o (scratchpad with news) | 0.2002 | 930 | 0.0% | 100.0% |
| Qwen1.5-110B-Chat (superforecaster with news 1) | 0.2016 | 930 | 0.0% | 100.0% |
| Mixtral-8x22B-Instruct-V0.1 (superforecaster with news 1) | 0.2017 | 930 | 0.0% | 100.0% |
| Claude-3-Opus-20240229 (superforecaster with news 2) | 0.2028 | 930 | 0.0% | 100.0% |
| Mistral-Large-Latest (superforecaster with news 2) | 0.2030 | 892 | 4.1% | 97.9% |
| Claude-3-5-Sonnet-20240620 (superforecaster with news 2) | 0.2068 | 930 | 0.0% | 99.3% |
| Gemini-1.5-Pro (superforecaster with news 3) | 0.2070 | 930 | 0.0% | 100.0% |
| GPT-4-Turbo-2024-04-09 (superforecaster with news 1) | 0.2075 | 930 | 0.0% | 100.0% |
| Mixtral-8x22B-Instruct-V0.1 (scratchpad with news with freeze values) | 0.2083 | 930 | 0.0% | 100.0% |
| GPT-4o (superforecaster with news 3) | 0.2086 | 781 | 16.0% | 84.9% |
| Claude-3-Opus-20240229 (scratchpad with news with freeze values) | 0.2097 | 930 | 0.0% | 100.0% |
| Mixtral-8x22B-Instruct-V0.1 (scratchpad with news) | 0.2102 | 930 | 0.0% | 100.0% |
| Qwen1.5-110B-Chat (superforecaster with news 3) | 0.2103 | 797 | 14.3% | 87.5% |
| Claude-3-Opus-20240229 (superforecaster with news 3) | 0.2106 | 783 | 15.8% | 87.0% |
| Mistral-Large-Latest (scratchpad with news with freeze values) | 0.2108 | 930 | 0.0% | 100.0% |
| Claude-3-Opus-20240229 (scratchpad with news) | 0.2113 | 930 | 0.0% | 100.0% |
| Mistral-Large-Latest (scratchpad with news) | 0.2116 | 930 | 0.0% | 100.0% |
| Gemini-1.5-Pro (superforecaster with news 1) | 0.2118 | 930 | 0.0% | 100.0% |
| Claude-3-5-Sonnet-20240620 (scratchpad with SECOND news) | 0.2136 | 929 | 0.1% | 100.0% |
| GPT-4o (superforecaster with news 1) | 0.2138 | 930 | 0.0% | 100.0% |
| Mistral-Large-Latest (superforecaster with news 1) | 0.2141 | 930 | 0.0% | 100.0% |
| Mixtral-8x22B-Instruct-V0.1 (superforecaster with news 3) | 0.2173 | 663 | 28.7% | 67.0% |
| Qwen1.5-110B-Chat (superforecaster with news 2) | 0.2191 | 876 | 5.8% | 94.1% |
| Gemini-1.5-Pro (superforecaster with news 2) | 0.2197 | 930 | 0.0% | 100.0% |
| Mistral-Large-Latest (superforecaster with news 3) | 0.2236 | 773 | 16.9% | 84.4% |
| Mixtral-8x22B-Instruct-V0.1 (superforecaster with news 2) | 0.2237 | 894 | 3.9% | 96.5% |
| Gemini-1.5-Flash (scratchpad with news with freeze values) | 0.2243 | 929 | 0.1% | 100.0% |
| Gemini-1.5-Flash (scratchpad with news) | 0.2274 | 929 | 0.1% | 100.0% |
| GPT-4-Turbo-2024-04-09 (superforecaster with news 2) | 0.2274 | 886 | 4.7% | 96.5% |
| Claude-2.1 (scratchpad with news with freeze values) | 0.2287 | 917 | 1.4% | 98.6% |
| Claude-2.1 (scratchpad with news) | 0.2296 | 913 | 1.8% | 97.1% |
| GPT-4o (scratchpad with SECOND news) | 0.2338 | 853 | 8.3% | 89.1% |
| Claude-2.1 (superforecaster with news 3) | 0.2345 | 848 | 8.8% | 91.0% |
| Claude-2.1 (superforecaster with news 1) | 0.2369 | 923 | 0.8% | 97.8% |
| Claude-2.1 (superforecaster with news 2) | 0.2380 | 894 | 3.9% | 96.7% |
| Mixtral-8x7B-Instruct-V0.1 (superforecaster with news 2) | 0.2415 | 883 | 5.1% | 92.6% |
| Claude-3-Haiku-20240307 (superforecaster with news 2) | 0.2466 | 926 | 0.4% | 99.3% |
| Gemini-1.5-Flash (superforecaster with news 3) | 0.2468 | 721 | 22.5% | 81.0% |
| GPT-4o (superforecaster with news 2) | 0.2477 | 926 | 0.4% | 97.9% |
| Gemini-1.5-Flash (superforecaster with news 1) | 0.2526 | 930 | 0.0% | 99.8% |
| Gemini-1.5-Flash (superforecaster with news 2) | 0.2556 | 929 | 0.1% | 99.3% |
| Mixtral-8x7B-Instruct-V0.1 (scratchpad with news) | 0.2571 | 894 | 3.9% | 97.1% |
| Mixtral-8x7B-Instruct-V0.1 (superforecaster with news 1) | 0.2573 | 886 | 4.7% | 95.3% |
| Mixtral-8x7B-Instruct-V0.1 (superforecaster with news 3) | 0.2577 | 880 | 5.4% | 91.5% |
| Mixtral-8x7B-Instruct-V0.1 (scratchpad with news with freeze values) | 0.2590 | 894 | 3.9% | 96.7% |
| Claude-3-Haiku-20240307 (superforecaster with news 3) | 0.2652 | 498 | 46.5% | 58.3% |
| Claude-3-Haiku-20240307 (scratchpad with news with freeze values) | 0.2778 | 930 | 0.0% | 100.0% |
| Claude-3-Haiku-20240307 (scratchpad with news) | 0.2791 | 930 | 0.0% | 100.0% |
| Claude-3-Haiku-20240307 (superforecaster with news 1) | 0.3111 | 930 | 0.0% | 100.0% |

## Encompassing fits

`o ~ logit(p_m) + [logit(p_h) - logit(p_m)]`, `models.encompassing` (v1), clip (0.01, 0.99), question-clustered SEs, on targets covered (non-imputed) by both the news variant and benchmark (a). `beta_a_same` is benchmark (a) refit on the same targets. `diff` = beta_news - beta_a_same with a question-level cluster bootstrap percentile interval (2000 draws, seed 20260906; both coefficients refit on the same draw).

| model | group | beta_news | coef_logit_news | beta_a_same | diff | n_targets | n_questions | clipped_news | clipped_a | clipped_human | boot_fail |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sonnet 3.5 (scratchpad with news) | S | 1.41 [0.74, 2.08] | 2.24 | 1.79 [1.04, 2.53] | -0.38 [-0.81, -0.06] | 578 | 162 | 22 | 7 | 160 | 0 |
| Sonnet 3.5 (scratchpad with news) | P | 0.81 [0.22, 1.40] | 2.02 | 0.97 [0.24, 1.70] | -0.16 [-0.50, 0.16] | 578 | 162 | 22 | 7 | 0 | 0 |
| Sonnet 3.5 (scratchpad with news with freeze values) | S | 1.41 [0.73, 2.10] | 2.10 | 1.79 [1.04, 2.53] | -0.37 [-0.76, -0.08] | 578 | 162 | 24 | 7 | 160 | 0 |
| Sonnet 3.5 (scratchpad with news with freeze values) | P | 0.73 [0.11, 1.35] | 1.96 | 0.97 [0.24, 1.70] | -0.24 [-0.58, 0.09] | 578 | 162 | 24 | 7 | 0 | 0 |
| Sonnet 3.5 (scratchpad with SECOND news) | S | 1.67 [0.95, 2.39] | 1.59 | 1.79 [1.04, 2.53] | -0.12 [-0.54, 0.28] | 578 | 162 | 11 | 7 | 160 | 0 |
| Sonnet 3.5 (scratchpad with SECOND news) | P | 1.51 [0.91, 2.11] | 2.04 | 0.97 [0.24, 1.70] | 0.54 [0.21, 0.89] | 578 | 162 | 11 | 7 | 0 | 0 |
| Sonnet 3.5 (superforecaster with news 1) | S | 1.48 [0.82, 2.14] | 2.08 | 1.79 [1.04, 2.53] | -0.31 [-0.82, 0.05] | 578 | 162 | 26 | 7 | 160 | 0 |
| Sonnet 3.5 (superforecaster with news 1) | P | 1.11 [0.44, 1.78] | 2.02 | 0.97 [0.24, 1.70] | 0.14 [-0.31, 0.58] | 578 | 162 | 26 | 7 | 0 | 0 |

fast_logit vs models.encompassing on the full common samples: max |Δ human coefficient| = 8.88e-16.

The superforecaster rows are reported but are not identification evidence on their own (group stage).

## Checklist

- Spec commit: `751e0fb68d0d8131044cea92b88375bdf865c499`. Repo HEAD at run: `7d5a0b784ba9943e3a2dfaa72e32c16fd51ce006`. Amendment 5 results not committed.
- Locked reading: restated above.
- Branch (best passing news variant, `Sonnet 3.5 (superforecaster with news 1)`): 1 — news variant's selection-set Q is worse than benchmark (a)'s: Amendment 5 cannot narrow the information-set confound.
- Reproduction check (untouched v1 H2 path, pooled, clip (0.01, 0.99)): S 1.79 [1.04, 2.53] vs locked 1.79 [1.04, 2.53] — match; P 0.97 [0.24, 1.70] vs locked 0.97 [0.24, 1.70] — match.
