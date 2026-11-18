# Method submissions

[View submitted methods](received/README.md)

For **Causal Mediation Analysis**, use the [benchmark card](https://statsinference.github.io/mediation/) to download the development kit and the official observed tables. Complete the [mediation method form](https://github.com/Statsinference/statsinference.github.io/issues/new?template=mediation-method.yml) with your version, run instructions or analysis procedure, interval construction and training exposure. You can submit a public GitHub repository or Hugging Face model for review, or a public method card with linked predictions on the official tables. Development results are optional. Official predictions include one row per table with `table_id,estimate,ci_lower,ci_upper`.

For other domains, submit a Hugging Face model link using **Submit your method** on the [website](https://statsinference.github.io/), then confirm the prefilled issue on GitHub. A GitHub account is required. Submissions are public.

The intake workflow archives valid submissions as JSON in `received/` and adds them to the list above. The research repository periodically imports model-link records. Official evaluation and leaderboard results require a separate maintainer review and run.
