# Leaderboard results

`data/results.json` starts empty on purpose. Do not add simulated results or publish unapproved experiments.

Each `suites` entry represents one comparable evaluation suite with a unique `id`, a `domain`, a human-readable `label`, an explicit `target` (estimand), and a `rows` array. Optional metadata: `sample_size`, `nominal_coverage` (fraction in (0, 1)), `aggregation`, `hardware`, and `timing_scope`.

Domain IDs: `ate`, `cate`, `mediation`, `iv`, `proximal`, `did_sc`, `nonparametric_regression`, `quantile`, `semi_supervised`, `missing_data`.

Each row uses `group` (`ID` or `OOD`), `method`, `method_id` (recommended), `family` (`pfn` or `classical`), optional `org`, and the metrics `bias`, `variance`, `rmse`, `length`, `coverage`, `time_s`. Metrics must be finite numbers or null; all except bias must be nonnegative. Coverage uses a fraction between 0 and 1, not percentage points. Unknown metrics are null, never zero. Variance is not SE. Use distinct method IDs for distinct configurations.

The page reads this JSON without building. It does not compute or invent metrics. Methods are sorted within their own split and evaluation suite; ID and OOD are never averaged. Different estimands belong in separate suites. Explain the reference training stage and held-out units of an OOD split in release metadata.

## Local use

Run `python3 -m http.server 8000` in this directory. The public site consists of `index.html`, `assets/`, and `data/`. Never place private archives, datasets, tokens, or unpublished experimental results anywhere in this public repository.
