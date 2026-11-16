# StatsArena website

Public website for Statistical Inference Arena. This repository contains presentation code only. It is separate from the private research repository: no DGP archives, generators, training data, or unpublished evaluation results are copied here.

## Website

The site provides independent leaderboards for ten domains: ATE, CATE, Mediation, Instrumental Variables, Proximal Causal Inference, DiD / Synthetic Control, Nonparametric Regression, Quantile Inference, Semi-Supervised Inference, and Missing Data.

Each leaderboard separates ID and OOD and displays Bias, Variance, RMSE, Length, Coverage, and Time. No evaluation results are published yet. Empty states are intentional, not simulated scores.

## Publishing

Enable GitHub Pages in **Settings → Pages** and choose **GitHub Actions** as the source. The deployment workflow publishes only the website files. The intended URL is `https://statsinference.github.io/`; repository creation alone does not activate the site.
