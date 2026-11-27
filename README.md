# Tracing Technical Debt Footprints in Large-Scale Microservices Systems



The study measures code-level technical debt at every commit across nine open-source
microservice repositories, then asks three questions of the resulting time series: how
debt evolves, whether it relates to the number of services, and which development
activities produce the largest increases.

## What is here

    pipeline/pipeline.py            per-commit collection: checkout, build, SonarQube scan, append a row
    pipeline/pipeline_mac_archived.py   earlier macOS variant, retained because its JDK cascade differs
    pipeline/statistical_analysis.py    ADF stationarity, STL decomposition, Granger causality
    pipeline/compute_spikes.py          gap-aware largest single-commit increases, plus the artefact audit
    pipeline/visualise_footprint.py     per-repository debt footprints and the cross-repository comparison
    pipeline/plot_cross_section.py      absolute debt against debt density at the latest commit
    pipeline/figstyle.py                shared style module for the hand-drawn diagrams
    pipeline/make_figure_*.py           the diagrams, reproducible from the style module
    pipeline/check_health.sh            SonarQube availability check used during collection
    results/*_results.csv               one row per commit, per repository
    results/statistical_analysis_summary.csv    the per-repository statistical results
    results/figures/                    every figure in the dissertation
    results/screenshots/                SonarQube and td-agent captures

## The dataset

13,141 commits across nine repositories, January 2015 to July 2026. 12,815 carry a
usable SQALE measurement, which is 97.5 per cent. Of the remainder, 304 are scan
failures, all in taotao-cloud-project, 21 are analysis timeouts, and one
geoserver-cloud commit has a valid build status but no usable value.

Each row records the SQALE index in remediation minutes, non-comment lines of code,
file count, cyclomatic complexity, code smells, bugs, vulnerabilities, microservice
count, build status and the JDK used. Build status and lines of code were recorded for
transparency rather than for analysis, and it is that decision which later made the
analysis scope artefacts detectable.

## Reproducing the analysis

The CSVs are included, so the analysis runs without re-collecting anything:

    pip install pandas statsmodels matplotlib numpy
    python3 pipeline/statistical_analysis.py         # RQ1 and RQ2
    python3 pipeline/compute_spikes.py               # RQ3, with the artefact audit
    python3 pipeline/visualise_footprint.py --repo piggymetrics
    python3 pipeline/visualise_footprint.py --mode compare

Output is deterministic: regenerating the figures from the committed CSVs reproduces
them byte for byte.

## Re-running collection

Collection needs a SonarQube 9.9 LTS Community Edition server, sonar-scanner, and
both Java 11 and Java 17 available. One pass over 13,141 commits takes several weeks
of continuous machine time. Credentials are read from the environment:

    export SONAR_HOST=http://localhost:9000
    export SONAR_TOKEN=...        # scan permission
    export SONAR_API_USER=...     # browse permission, for metric reads
    export SONAR_API_PASS=...
    python3 pipeline/pipeline.py --repo piggymetrics

Rows are appended as each commit completes and already-processed hashes are skipped,
so a run can be interrupted and resumed.

## The language model agent

The exploratory strand uses a separate tool, td-agent, maintained at
https://github.com/boluwatifeajayi/td-agent

## Analysed repositories

piggymetrics, train-ticket, geoserver-cloud, robot-shop, microservices-demo,
spring-petclinic-microservices, DeathStarBench, light-4j, taotao-cloud-project. A tenth,
erda, appears in the agent strand only, having been withdrawn from SonarQube collection
on time grounds.

All ten are public and were analysed under licences permitting analysis and the
publication of findings. Their source is not redistributed here; only the measurements
taken from it.

## Note on scope

This package holds the collection pipeline, the analysis code and the measurements. It
does not include the dissertation text, third-party papers or any teaching material.
