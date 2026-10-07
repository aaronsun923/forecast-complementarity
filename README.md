# forecast-complementarity

Analysis code and locked specifications for a study of forecast encompassing and combination between human medians and a language model, on the ForecastBench round of 2024-07-21.

Paper: *Human Medians and a Language-Model Forecast: Encompassing and Combination on One ForecastBench Round*, https://doi.org/10.5281/zenodo.22589676 (current version: https://doi.org/10.5281/zenodo.23147918). Earlier versions of this record carry the title *Where the Benchmark Can Err*.

Code archive: https://doi.org/10.5281/zenodo.22600832

## Contents

- `specs/` the analysis specifications, each locked and pushed before the analysis it governs, with dated amendments
- `code/` the pipeline
- `docs/` the pilot and full-run reports, the SPEC v3 amendment reports, and the figures
- `paper/` the current paper PDF

## Reproduce

`notebooks/reproduce_v9.ipynb` reruns the pipeline from the raw data and checks every number in paper v9 against the recomputed value. The paper numbers are transcribed in `notebooks/paper_numbers_v9.json`. `notebooks/reproduce_v9.nbconvert.ipynb` is the executed copy.

The data are not in this repository. They live under `config.STUDY_ROOT` (default `~/Desktop/forecast-study`; edit `code/config.py` to move it). `data/PROVENANCE.md` there records each artifact. The fetch steps:

1. **ForecastBench datasets repository**, at the pinned commit:
   ```
   cd ~/Desktop/forecast-study
   git clone https://github.com/forecastingresearch/forecastbench-datasets
   git -C forecastbench-datasets checkout 68932db171f5e13349d9bda0dd9f96fcf6e227e2
   ```
   `datasets/forecast_sets/2024-07-21/2024-07-21.ForecastBench.human_public_individual.json` is stored in Git LFS. Without `git-lfs` the clone holds a 130-byte pointer. Install `git-lfs` and run `git lfs pull`, or fetch the object through the GitHub LFS batch API. It must hash to sha256 `4b3661081a54be787832f89051b19c2ada2f8c96396d692db3f5a753bec2b1fd` (23,526,935 bytes).
2. **The processed forecast-set tarball**, into `data/raw/`. Only `processed_forecast_sets.tar.gz` is required. The 2026-09-06 snapshot is archived at https://doi.org/10.5281/zenodo.23201267. Download `processed_forecast_sets.tar.gz` from there into `data/raw/`, then:
   ```
   cd data/raw
   tar xzf processed_forecast_sets.tar.gz      # -> forecastbench-processed-forecast-sets/
   ```
   Its sha256 must equal `config.TARBALL_SHA256["processed_forecast_sets.tar.gz"]` (also in `data/PROVENANCE.md` §1). Do not substitute a fresh download from forecastbench.org: the publisher regenerates the file nightly and keeps no versions, so a copy made after 2026-09-06 will not match. `forecast_sets.tar.gz` is not read by the pipeline. If it is present in `data/raw/` it must match its recorded hash; if it is absent the notebook prints a warning and continues.
3. **Environment**: Python 3.9.6 and `pip install -r requirements.txt`.

Then, from the repository root:

```
jupyter nbconvert --execute --to notebook notebooks/reproduce_v9.ipynb
```

The notebook stops with a message if the data are absent, the datasets commit differs, or a tarball hash differs. Otherwise it runs `full.py`, `v2_full.py`, `amendment4_h5.py`, `amendment5.py`, `amendment5b.py` and `amendment6.py` in that order, unedited. Their reports, figures and checkpoints go to a fresh `config.STUDY_ROOT/repro_v9/`, never to `docs/` or `data/derived/`. The notebook ends with the match table. Expected runtime: about 1 h 45 min (104 min measured) on an Apple M-series laptop, most of it in `v2_full.py`.

## Related

`docs/` also carries a working note that states the quantity this study and two companion studies measure: *Measuring What a Human Adds to a Machine Baseline: A Problem Statement*, https://doi.org/10.5281/zenodo.22822929

Companion studies: chess, https://doi.org/10.5281/zenodo.22267000 ; image classification, https://doi.org/10.5281/zenodo.22822332
