# CI failure classifier evaluation

- Created: 2026-09-15T15:08:00+00:00
- Train / test samples: 653 / 291
- Excerpt profile: `default`; test samples from source: `all`
- Test labels: authentication=6, compilation=31, dependency=31, infrastructure=22, other=98, test_assertion=103
- labels.jsonl sha256 (first 16): `f75bbd02679abf4c`; split created 2026-09-14T10:32:49+00:00

## Uncertainty and significance

95% confidence intervals from a cluster bootstrap (1000 resamples of whole
repo/workflow groups, since runs of one workflow are not independent):

| Method | Samples | Accuracy [95% CI] | Macro F1 [95% CI] |
| --- | --- | --- | --- |
| rules | 291 | 0.34 [0.22, 0.46] | 0.45 [0.26, 0.53] |
| tfidf | 291 | 0.57 [0.44, 0.70] | 0.30 [0.23, 0.46] |
| llm | 291 | 0.72 [0.61, 0.81] | 0.71 [0.60, 0.78] |
| hybrid | 291 | 0.75 [0.64, 0.84] | 0.71 [0.59, 0.79] |

Exact McNemar test on the samples both methods scored (p < 0.05: the accuracy difference is unlikely to be chance;
samples are treated as independent here, so read borderline p-values with care):

| A vs B | Samples | Only A right | Only B right | p-value |
| --- | --- | --- | --- | --- |
| rules vs tfidf | 291 | 23 | 91 | 9.3e-11 |
| rules vs llm | 291 | 23 | 133 | 5.1e-20 |
| rules vs hybrid | 291 | 16 | 135 | 1.2e-24 |
| tfidf vs llm | 291 | 35 | 77 | 9e-05 |
| tfidf vs hybrid | 291 | 26 | 77 | 4.9e-07 |
| llm vs hybrid | 291 | 0 | 9 | 0.0039 |

## Cross-validation

Grouped, stratified 5-fold cross-validation over all 944 labelled samples (whole repo/workflow
groups per fold; TF-IDF refitted on the other folds). Per-fold values are in `cv_folds.csv`.

| Method | Folds | Samples scored | Accuracy (mean ± sd) | Macro F1 (mean ± sd) | Abstention (mean) |
| --- | --- | --- | --- | --- | --- |
| rules | 5 | 944 | 0.42 ± 0.07 | 0.52 ± 0.09 | 0.48 |
| tfidf | 5 | 944 | 0.63 ± 0.05 | 0.43 ± 0.08 | 0.00 |
| llm | 5 | 333 | 0.71 ± 0.11 | 0.69 ± 0.06 | 0.08 |
| hybrid | 5 | 333 | 0.74 ± 0.09 | 0.69 ± 0.07 | 0.00 |

> llm is scored only on the 333 samples that already have stored answers (`llm-run`).
> hybrid is scored only on the 333 samples that already have stored answers (`llm-run`).

## Baseline 1 - keyword rules

- Accuracy: **0.34** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.57
- Accuracy when answered: 0.79
- Macro F1: 0.45
- Runtime: 3.9 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.69 | 0.35 | 0.47 | 31 | 16 |
| test_assertion | 0.77 | 0.62 | 0.69 | 103 | 83 |
| dependency | 1.00 | 0.19 | 0.32 | 31 | 6 |
| authentication | 1.00 | 1.00 | 1.00 | 6 | 6 |
| infrastructure | 0.00 | 0.00 | 0.00 | 22 | 1 |
| other | 0.92 | 0.12 | 0.22 | 98 | 13 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.27 | 0.62 |
| github-actions (targeted-auth) | 7 | 0.86 | 0.14 |
| logchunks | 229 | 0.34 | 0.57 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 11 | 9 | 0 | 0 | 1 | 0 | 10 |
| test_assertion | 0 | 64 | 0 | 0 | 0 | 1 | 38 |
| dependency | 3 | 2 | 6 | 0 | 0 | 0 | 20 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 1 | 0 | 0 | 0 | 0 | 21 |
| other | 2 | 7 | 0 | 0 | 0 | 12 | 77 |

Examples of mistakes:

- `logchunks__processone__ejabberd__555702367` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__557756393` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__566947386` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__570754006` label=other predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `microsoft__vscode__31801400244` label=dependency predicted=compilation - ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31821965820` label=dependency predicted=unknown
- `microsoft__vscode__31954973692` label=compilation predicted=infrastructure - fatal: unable to access 'https://github.com/microsoft/vscode-smoketest-express/': Could not resolve host: github.com
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - [eslint                   ] Error: eslint failed with 2 warnings and/or errors
- `dotnet__aspire__34767579964` label=dependency predicted=test_assertion - Build FAILED.
- `python__cpython__34115243281` label=infrastructure predicted=unknown

## Baseline 2 - TF-IDF + logistic regression

- Accuracy: **0.57** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.00
- Accuracy when answered: 0.57
- Macro F1: 0.30
- Runtime: 6.5 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.21 | 0.10 | 0.13 | 31 | 14 |
| test_assertion | 0.59 | 0.85 | 0.70 | 103 | 150 |
| dependency | 0.40 | 0.06 | 0.11 | 31 | 5 |
| authentication | 0.00 | 0.00 | 0.00 | 6 | 10 |
| infrastructure | 1.00 | 0.09 | 0.17 | 22 | 2 |
| other | 0.65 | 0.73 | 0.69 | 98 | 110 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.35 | 0.00 |
| github-actions (targeted-auth) | 7 | 0.00 | 0.00 |
| logchunks | 229 | 0.65 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 3 | 20 | 1 | 0 | 0 | 7 | 0 |
| test_assertion | 3 | 88 | 2 | 0 | 0 | 10 | 0 |
| dependency | 1 | 15 | 2 | 0 | 0 | 13 | 0 |
| authentication | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| infrastructure | 0 | 11 | 0 | 1 | 2 | 8 | 0 |
| other | 1 | 16 | 0 | 9 | 0 | 72 | 0 |

Examples of mistakes:

- `logchunks__processone__ejabberd__557756393` label=other predicted=compilation - p=0.29
- `microsoft__vscode__31728854334` label=compilation predicted=test_assertion - p=0.23
- `microsoft__vscode__31801400244` label=dependency predicted=test_assertion - p=0.26
- `microsoft__vscode__31821965820` label=dependency predicted=other - p=0.23
- `python__cpython__33986657598` label=compilation predicted=test_assertion - p=0.23
- `microsoft__vscode__31954973692` label=compilation predicted=test_assertion - p=0.29
- `microsoft__vscode__31959446031` label=compilation predicted=test_assertion - p=0.33
- `microsoft__vscode__31975340271` label=compilation predicted=test_assertion - p=0.26
- `dotnet__aspire__34767579964` label=dependency predicted=test_assertion - p=0.24
- `microsoft__vscode__34235077561` label=dependency predicted=other - p=0.24

## Method 3 - LLM (OpenRouter)

- Accuracy: **0.72** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.08
- Accuracy when answered: 0.78
- Macro F1: 0.71
- Model: `nvidia/nemotron-3-super-120b-a12b:free`, prompt `v1`
- Tokens per sample: 1528.85 prompt + 297.32 completion; total cost $0.0000
- Median latency: 4.46 s; unparseable replies: 8

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.68 | 0.68 | 0.68 | 31 | 31 |
| test_assertion | 0.78 | 0.80 | 0.79 | 103 | 105 |
| dependency | 0.69 | 0.71 | 0.70 | 31 | 32 |
| authentication | 0.75 | 1.00 | 0.86 | 6 | 8 |
| infrastructure | 0.45 | 0.41 | 0.43 | 22 | 20 |
| other | 0.97 | 0.70 | 0.82 | 98 | 71 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.67 | 0.11 |
| github-actions (targeted-auth) | 7 | 1.00 | 0.00 |
| logchunks | 229 | 0.72 | 0.08 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 21 | 1 | 0 | 0 | 1 | 1 | 7 |
| test_assertion | 2 | 82 | 3 | 0 | 3 | 1 | 12 |
| dependency | 6 | 2 | 22 | 1 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 8 | 0 | 0 | 9 | 0 | 5 |
| other | 2 | 12 | 7 | 1 | 7 | 69 | 0 |

Examples of mistakes:

- `logchunks__processone__ejabberd__555699963` label=test_assertion predicted=unknown - conf=? | unparseable reply
- `logchunks__processone__ejabberd__555702367` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/cache_tab/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__556990927` label=test_assertion predicted=unknown - conf=? | unparseable reply
- `logchunks__processone__ejabberd__557756393` label=other predicted=compilation - conf=0.80 | ERROR: xref failed while processing /home/travis/build/processone/ejabberd: rebar_abort
- `logchunks__processone__ejabberd__558529443` label=test_assertion predicted=unknown - conf=? | unparseable reply
- `logchunks__processone__ejabberd__566947386` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stun/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__570754006` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stringprep/': Failed to connect to github.com port 443: Connection timed out
- `microsoft__vscode__31801400244` label=dependency predicted=compilation - conf=0.95 | ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31821965820` label=dependency predicted=authentication - conf=0.95 | npm error [foundry-local] Installation failed: Failed to download Microsoft.AI.Foundry.Local.Core 1.2.3 from any configured feed (api.nuget.org, pkg
- `python__cpython__33789566126` label=test_assertion predicted=compilation - conf=0.95 | IndentationError: unindent does not match any outer indentation level

## Method 4 - hybrid (LLM, TF-IDF when the LLM abstains)

- Accuracy: **0.75** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.00
- Accuracy when answered: 0.75
- Macro F1: 0.71
- Runtime: 0.2 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.68 | 0.68 | 0.68 | 31 | 31 |
| test_assertion | 0.78 | 0.88 | 0.83 | 103 | 116 |
| dependency | 0.69 | 0.71 | 0.70 | 31 | 32 |
| authentication | 0.75 | 1.00 | 0.86 | 6 | 8 |
| infrastructure | 0.45 | 0.41 | 0.43 | 22 | 20 |
| other | 0.82 | 0.70 | 0.76 | 98 | 84 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.69 | 0.00 |
| github-actions (targeted-auth) | 7 | 1.00 | 0.00 |
| logchunks | 229 | 0.76 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 21 | 3 | 0 | 0 | 1 | 6 | 0 |
| test_assertion | 2 | 91 | 3 | 0 | 3 | 4 | 0 |
| dependency | 6 | 2 | 22 | 1 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 8 | 0 | 0 | 9 | 5 | 0 |
| other | 2 | 12 | 7 | 1 | 7 | 69 | 0 |

Examples of mistakes:

- `logchunks__processone__ejabberd__555702367` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/cache_tab/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__557756393` label=other predicted=compilation - conf=0.80 | ERROR: xref failed while processing /home/travis/build/processone/ejabberd: rebar_abort
- `logchunks__processone__ejabberd__566947386` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stun/': Failed to connect to github.com port 443: Connection timed out
- `logchunks__processone__ejabberd__570754006` label=other predicted=infrastructure - conf=0.95 | fatal: unable to access 'https://github.com/processone/stringprep/': Failed to connect to github.com port 443: Connection timed out
- `microsoft__vscode__31801400244` label=dependency predicted=compilation - conf=0.95 | ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31821965820` label=dependency predicted=authentication - conf=0.95 | npm error [foundry-local] Installation failed: Failed to download Microsoft.AI.Foundry.Local.Core 1.2.3 from any configured feed (api.nuget.org, pkg
- `python__cpython__33789566126` label=test_assertion predicted=compilation - conf=0.95 | IndentationError: unindent does not match any outer indentation level
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - conf=0.95 | ERROR: "eslint" exited with 1.
- `python__cpython__34752783005` label=other predicted=compilation - conf=0.95 | Tools/peg_generator/pegen/c_generator.py:817: error:^[(B Item ^[(B"Group"^[(B of ^[(B"Leaf | Group | Opt | Repeat | Forced | Lookahead | Rhs | Cut"^
- `python__cpython__34746973474` label=infrastructure predicted=other - tfidf fallback p=0.21 (primary: conf=0.20 | Prebuild template deployment failed.)

## Triage time

No sessions yet. Run `python -m ci_classifier triage --participant <name>` to measure it.
