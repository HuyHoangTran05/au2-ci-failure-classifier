# CI failure classifier evaluation

- Created: 2026-09-16T02:17:07+00:00
- Train / test samples: 653 / 291
- Excerpt profile: `default`; test samples from source: `all`
- Test labels: authentication=6, compilation=42, dependency=21, infrastructure=28, other=87, test_assertion=107
- labels.jsonl sha256 (first 16): `196c4834d0e086e0`; split created 2026-09-14T10:32:49+00:00

## Uncertainty and significance

95% confidence intervals from a cluster bootstrap (1000 resamples of whole
repo/workflow groups, since runs of one workflow are not independent):

| Method | Samples | Accuracy [95% CI] | Macro F1 [95% CI] |
| --- | --- | --- | --- |
| rules | 291 | 0.34 [0.23, 0.46] | 0.46 [0.27, 0.54] |
| tfidf | 291 | 0.56 [0.43, 0.69] | 0.30 [0.23, 0.44] |
| llm | 291 | 0.74 [0.63, 0.84] | 0.74 [0.63, 0.83] |
| hybrid | 291 | 0.77 [0.66, 0.86] | 0.73 [0.62, 0.83] |

Exact McNemar test on the samples both methods scored (p < 0.05: the accuracy difference is unlikely to be chance;
samples are treated as independent here, so read borderline p-values with care):

| A vs B | Samples | Only A right | Only B right | p-value |
| --- | --- | --- | --- | --- |
| rules vs tfidf | 291 | 25 | 90 | 8.4e-10 |
| rules vs llm | 291 | 21 | 137 | 4.7e-22 |
| rules vs hybrid | 291 | 14 | 139 | 4.7e-27 |
| tfidf vs llm | 291 | 32 | 83 | 2.2e-06 |
| tfidf vs hybrid | 291 | 23 | 83 | 3.8e-09 |
| llm vs hybrid | 291 | 0 | 9 | 0.0039 |

## Cross-validation

Grouped, stratified 5-fold cross-validation over all 944 labelled samples (whole repo/workflow
groups per fold; TF-IDF refitted on the other folds). Per-fold values are in `cv_folds.csv`.

| Method | Folds | Samples scored | Accuracy (mean ± sd) | Macro F1 (mean ± sd) | Abstention (mean) |
| --- | --- | --- | --- | --- | --- |
| rules | 5 | 944 | 0.42 ± 0.10 | 0.52 ± 0.11 | 0.48 |
| tfidf | 5 | 944 | 0.61 ± 0.06 | 0.42 ± 0.11 | 0.00 |
| llm | 5 | 333 | 0.71 ± 0.07 | 0.66 ± 0.07 | 0.08 |
| hybrid | 5 | 333 | 0.76 ± 0.08 | 0.69 ± 0.09 | 0.00 |

> llm is scored only on the 333 samples that already have stored answers (`llm-run`).
> hybrid is scored only on the 333 samples that already have stored answers (`llm-run`).

## Baseline 1 - keyword rules

- Accuracy: **0.34** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.57
- Accuracy when answered: 0.79
- Macro F1: 0.46
- Runtime: 2.2 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.75 | 0.29 | 0.41 | 42 | 16 |
| test_assertion | 0.78 | 0.61 | 0.68 | 107 | 83 |
| dependency | 1.00 | 0.29 | 0.44 | 21 | 6 |
| authentication | 1.00 | 1.00 | 1.00 | 6 | 6 |
| infrastructure | 0.00 | 0.00 | 0.00 | 28 | 1 |
| other | 0.77 | 0.11 | 0.20 | 87 | 13 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.31 | 0.62 |
| github-actions (targeted-auth) | 7 | 0.86 | 0.14 |
| logchunks | 229 | 0.33 | 0.57 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 12 | 9 | 0 | 0 | 1 | 0 | 20 |
| test_assertion | 2 | 65 | 0 | 0 | 0 | 1 | 39 |
| dependency | 2 | 2 | 6 | 0 | 0 | 0 | 11 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 3 | 0 | 0 | 0 | 2 | 23 |
| other | 0 | 4 | 0 | 0 | 0 | 10 | 73 |

Examples of mistakes:

- `logchunks__processone__ejabberd__554568247` label=infrastructure predicted=test_assertion - $ grep -q 'TEST COMPLETE,.* 0 failed' logs/raw.log
- `logchunks__processone__ejabberd__555702367` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__557756393` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__566947386` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__570754006` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `microsoft__vscode__31821965820` label=dependency predicted=unknown
- `microsoft__vscode__31954973692` label=compilation predicted=infrastructure - fatal: unable to access 'https://github.com/microsoft/vscode-smoketest-express/': Could not resolve host: github.com
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - [eslint                   ] Error: eslint failed with 2 warnings and/or errors
- `dotnet__aspire__34767579964` label=dependency predicted=test_assertion - Build FAILED.
- `python__cpython__34115243281` label=infrastructure predicted=unknown

## Baseline 2 - TF-IDF + logistic regression

- Accuracy: **0.56** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.00
- Accuracy when answered: 0.56
- Macro F1: 0.30
- Runtime: 2.5 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.29 | 0.10 | 0.14 | 42 | 14 |
| test_assertion | 0.59 | 0.83 | 0.69 | 107 | 150 |
| dependency | 0.40 | 0.10 | 0.15 | 21 | 5 |
| authentication | 0.00 | 0.00 | 0.00 | 6 | 10 |
| infrastructure | 1.00 | 0.07 | 0.13 | 28 | 2 |
| other | 0.61 | 0.77 | 0.68 | 87 | 110 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.35 | 0.00 |
| github-actions (targeted-auth) | 7 | 0.00 | 0.00 |
| logchunks | 229 | 0.63 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 4 | 26 | 1 | 0 | 0 | 11 | 0 |
| test_assertion | 3 | 89 | 1 | 0 | 0 | 14 | 0 |
| dependency | 0 | 11 | 2 | 0 | 0 | 8 | 0 |
| authentication | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| infrastructure | 0 | 14 | 1 | 1 | 2 | 10 | 0 |
| other | 1 | 10 | 0 | 9 | 0 | 67 | 0 |

Examples of mistakes:

- `logchunks__processone__ejabberd__554568247` label=infrastructure predicted=test_assertion - p=0.27
- `logchunks__processone__ejabberd__557756393` label=other predicted=compilation - p=0.29
- `microsoft__vscode__31728854334` label=compilation predicted=test_assertion - p=0.23
- `microsoft__vscode__31801400244` label=compilation predicted=test_assertion - p=0.26
- `microsoft__vscode__31821965820` label=dependency predicted=other - p=0.23
- `python__cpython__33986657598` label=compilation predicted=test_assertion - p=0.23
- `microsoft__vscode__31954973692` label=compilation predicted=test_assertion - p=0.29
- `microsoft__vscode__31959446031` label=compilation predicted=test_assertion - p=0.33
- `microsoft__vscode__31975340271` label=compilation predicted=test_assertion - p=0.26
- `dotnet__aspire__34767579964` label=dependency predicted=test_assertion - p=0.24

## Method 3 - LLM (OpenRouter)

- Accuracy: **0.74** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.08
- Accuracy when answered: 0.81
- Macro F1: 0.74
- Model: `nvidia/nemotron-3-super-120b-a12b:free`, prompt `v1`
- Tokens per sample: 1528.85 prompt + 297.32 completion; total cost $0.0000
- Median latency: 4.46 s; unparseable replies: 8

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.87 | 0.64 | 0.74 | 42 | 31 |
| test_assertion | 0.80 | 0.79 | 0.79 | 107 | 105 |
| dependency | 0.56 | 0.86 | 0.68 | 21 | 32 |
| authentication | 0.75 | 1.00 | 0.86 | 6 | 8 |
| infrastructure | 0.60 | 0.43 | 0.50 | 28 | 20 |
| other | 0.96 | 0.78 | 0.86 | 87 | 71 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.71 | 0.11 |
| github-actions (targeted-auth) | 7 | 1.00 | 0.00 |
| logchunks | 229 | 0.74 | 0.08 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 27 | 3 | 4 | 0 | 1 | 0 | 7 |
| test_assertion | 3 | 84 | 3 | 0 | 2 | 3 | 12 |
| dependency | 0 | 2 | 18 | 1 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 9 | 2 | 0 | 12 | 0 | 5 |
| other | 1 | 7 | 5 | 1 | 5 | 68 | 0 |

Examples of mistakes:

- `logchunks__processone__ejabberd__554568247` label=infrastructure predicted=test_assertion - conf=0.90 | ERROR: xref failed while processing /home/travis/build/processone/ejabberd: rebar_abort
- `logchunks__processone__ejabberd__555699963` label=test_assertion predicted=unknown - conf=? | unparseable reply
- `logchunks__processone__ejabberd__555702367` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/cache_tab/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__556990927` label=test_assertion predicted=unknown - conf=? | unparseable reply
- `logchunks__processone__ejabberd__557756393` label=other predicted=compilation - conf=0.80 | ERROR: xref failed while processing /home/travis/build/processone/ejabberd: rebar_abort
- `logchunks__processone__ejabberd__558529443` label=test_assertion predicted=unknown - conf=? | unparseable reply
- `logchunks__processone__ejabberd__566947386` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stun/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__570754006` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stringprep/': Failed to connect to github.com port 443: Connection timed out
- `microsoft__vscode__31821965820` label=dependency predicted=authentication - conf=0.95 | npm error [foundry-local] Installation failed: Failed to download Microsoft.AI.Foundry.Local.Core 1.2.3 from any configured feed (api.nuget.org, pkg
- `python__cpython__33789566126` label=test_assertion predicted=compilation - conf=0.95 | IndentationError: unindent does not match any outer indentation level

## Method 4 - hybrid (LLM, TF-IDF when the LLM abstains)

- Accuracy: **0.77** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.00
- Accuracy when answered: 0.77
- Macro F1: 0.73
- Runtime: 0.2 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.87 | 0.64 | 0.74 | 42 | 31 |
| test_assertion | 0.80 | 0.87 | 0.83 | 107 | 116 |
| dependency | 0.56 | 0.86 | 0.68 | 21 | 32 |
| authentication | 0.75 | 1.00 | 0.86 | 6 | 8 |
| infrastructure | 0.60 | 0.43 | 0.50 | 28 | 20 |
| other | 0.81 | 0.78 | 0.80 | 87 | 84 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.73 | 0.00 |
| github-actions (targeted-auth) | 7 | 1.00 | 0.00 |
| logchunks | 229 | 0.77 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 27 | 5 | 4 | 0 | 1 | 5 | 0 |
| test_assertion | 3 | 93 | 3 | 0 | 2 | 6 | 0 |
| dependency | 0 | 2 | 18 | 1 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 9 | 2 | 0 | 12 | 5 | 0 |
| other | 1 | 7 | 5 | 1 | 5 | 68 | 0 |

Examples of mistakes:

- `logchunks__processone__ejabberd__554568247` label=infrastructure predicted=test_assertion - conf=0.90 | ERROR: xref failed while processing /home/travis/build/processone/ejabberd: rebar_abort
- `logchunks__processone__ejabberd__555702367` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/cache_tab/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__557756393` label=other predicted=compilation - conf=0.80 | ERROR: xref failed while processing /home/travis/build/processone/ejabberd: rebar_abort
- `logchunks__processone__ejabberd__566947386` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stun/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__570754006` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stringprep/': Failed to connect to github.com port 443: Connection timed out
- `microsoft__vscode__31821965820` label=dependency predicted=authentication - conf=0.95 | npm error [foundry-local] Installation failed: Failed to download Microsoft.AI.Foundry.Local.Core 1.2.3 from any configured feed (api.nuget.org, pkg
- `python__cpython__33789566126` label=test_assertion predicted=compilation - conf=0.95 | IndentationError: unindent does not match any outer indentation level
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - conf=0.95 | ERROR: "eslint" exited with 1.
- `python__cpython__34746973474` label=infrastructure predicted=other - tfidf fallback p=0.21 (primary: conf=0.20 | Prebuild template deployment failed.)
- `python__cpython__34748925258` label=infrastructure predicted=other - tfidf fallback p=0.21 (primary: conf=0.20 | Prebuild template deployment failed.)

## Triage time

No sessions yet. Run `python -m ci_classifier triage --participant <name>` to measure it.
