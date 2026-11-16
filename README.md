# Statistical Inference Arena

Public website: https://statsinference.github.io/

This repository contains website presentation code and approved summary results. It is separate from the private research repository. DGP archives, generators, training data, hidden evaluation configurations and internal PDFs are not copied here.

## Leaderboards

Independent leaderboards for ATE, CATE, Mediation, Instrumental Variables, Proximal Causal Inference, DiD / Synthetic Control, Nonparametric Regression, Quantile Inference, Semi-Supervised Inference, and Missing Data.

Each leaderboard separates ID and OOD and displays Bias, Variance, RMSE, Length, Coverage and Time. The Mediation leaderboard contains the first source-reported release. The other nine domains intentionally remain empty; no scores are simulated.

## Core Contributors

Equal recognition. Names are alphabetical by displayed name; no ranking is implied.

| Name | Affiliation |
| --- | --- |
| Jiaming Hu | Boston University |
| Shi Bo | Boston University |
| Zhiheng Zhang | Shanghai University of Finance and Economics |

## First reported results

The November 12, 2026 report by Shi Bo supplies MediPFN ID/Source-OOD results for NIE₁ at n = 500 and 95% nominal coverage. Values are transcribed, not independently rerun. Reported empirical SE is retained; approximate Variance is explicitly labeled as its square after source rounding.

Random Forest accuracy and interval metrics for this meeting run are not reported. Main-table entries are null, never zero. The 27-table paired CPU timing comparison uses a previous model and test set and is displayed separately. It is not pooled with the current GPU evaluation or used in its rankings and plots.

## Updating and publishing

Edit `data/results.json` using `DATA_FORMAT.md`. Keep the inline `results-data` JSON in `index.html` synchronized for initial rendering; the live page subsequently refreshes from `data/results.json`.

GitHub Pages is published by the existing deployment workflow. The published site consists of `index.html`, `.nojekyll`, `assets/` and `data/`. The verification workflow checks the deployed website in a browser, including equal contributor presentation and separation of the historical timing cohort.
