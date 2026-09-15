# CI failure classifier evaluation

- Created: 2026-09-15T10:14:51+00:00
- Train / test samples: 653 / 62
- Excerpt profile: `default`; test samples from source: `github-actions`
- Test labels: authentication=6, compilation=5, dependency=5, infrastructure=11, other=18, test_assertion=17
- labels.jsonl sha256 (first 16): `f6f0ebafe9ef9299`; split created 2026-09-14T10:32:49+00:00

## Uncertainty and significance

95% confidence intervals from a cluster bootstrap (1000 resamples of whole
repo/workflow groups, since runs of one workflow are not independent):

| Method | Samples | Accuracy [95% CI] | Macro F1 [95% CI] |
| --- | --- | --- | --- |
| rules | 62 | 0.34 [0.12, 0.60] | 0.49 [0.23, 0.59] |
| tfidf | 62 | 0.31 [0.13, 0.51] | 0.19 [0.10, 0.35] |
| llm | 62 | 0.71 [0.53, 0.87] | 0.73 [0.54, 0.86] |
| hybrid | 62 | 0.73 [0.55, 0.88] | 0.72 [0.54, 0.86] |

Exact McNemar test on the samples both methods scored (p < 0.05: the accuracy difference is unlikely to be chance;
samples are treated as independent here, so read borderline p-values with care):

| A vs B | Samples | Only A right | Only B right | p-value |
| --- | --- | --- | --- | --- |
| rules vs tfidf | 62 | 13 | 11 | 0.84 |
| rules vs llm | 62 | 2 | 25 | 5.6e-06 |
| rules vs hybrid | 62 | 1 | 25 | 8e-07 |
| tfidf vs llm | 62 | 6 | 31 | 4.1e-05 |
| tfidf vs hybrid | 62 | 5 | 31 | 1.3e-05 |
| llm vs hybrid | 62 | 0 | 1 | 1 |

## Baseline 1 - keyword rules

- Accuracy: **0.34** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.56
- Accuracy when answered: 0.78
- Macro F1: 0.49
- Runtime: 1.7 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.67 | 0.80 | 0.73 | 5 | 6 |
| test_assertion | 0.82 | 0.53 | 0.64 | 17 | 11 |
| dependency | 1.00 | 0.40 | 0.57 | 5 | 2 |
| authentication | 1.00 | 1.00 | 1.00 | 6 | 6 |
| infrastructure | 0.00 | 0.00 | 0.00 | 11 | 1 |
| other | 0.00 | 0.00 | 0.00 | 18 | 1 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.27 | 0.62 |
| github-actions (targeted-auth) | 7 | 0.86 | 0.14 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 4 | 0 | 0 | 0 | 1 | 0 | 0 |
| test_assertion | 0 | 9 | 0 | 0 | 0 | 1 | 7 |
| dependency | 1 | 1 | 2 | 0 | 0 | 0 | 1 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 1 | 0 | 0 | 0 | 0 | 10 |
| other | 1 | 0 | 0 | 0 | 0 | 0 | 17 |

Examples of mistakes:

- `microsoft__vscode__31801400244` label=dependency predicted=compilation - ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31821965820` label=dependency predicted=unknown
- `microsoft__vscode__31954973692` label=compilation predicted=infrastructure - fatal: unable to access 'https://github.com/microsoft/vscode-smoketest-express/': Could not resolve host: github.com
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - [eslint                   ] Error: eslint failed with 2 warnings and/or errors
- `dotnet__aspire__34767579964` label=dependency predicted=test_assertion - Build FAILED.
- `python__cpython__34115243281` label=infrastructure predicted=unknown
- `python__cpython__34752783005` label=other predicted=compilation - Tools/peg_generator/pegen/c_generator.py:817: error:^[(B Item ^[(B"Group"^[(B of
- `microsoft__vscode__31790622084` label=infrastructure predicted=unknown
- `microsoft__TypeScript__32991948166` label=infrastructure predicted=unknown
- `hashicorp__terraform-provider-aws__34274218483` label=infrastructure predicted=unknown

## Baseline 2 - TF-IDF + logistic regression

- Accuracy: **0.31** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.00
- Accuracy when answered: 0.31
- Macro F1: 0.19
- Runtime: 1.6 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.00 | 0.00 | 0.00 | 5 | 7 |
| test_assertion | 0.50 | 0.82 | 0.62 | 17 | 28 |
| dependency | - | 0.00 | 0.00 | 5 | 0 |
| authentication | 0.00 | 0.00 | 0.00 | 6 | 10 |
| infrastructure | 1.00 | 0.18 | 0.31 | 11 | 2 |
| other | 0.20 | 0.17 | 0.18 | 18 | 15 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.35 | 0.00 |
| github-actions (targeted-auth) | 7 | 0.00 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 0 | 5 | 0 | 0 | 0 | 0 | 0 |
| test_assertion | 1 | 14 | 0 | 0 | 0 | 2 | 0 |
| dependency | 0 | 2 | 0 | 0 | 0 | 3 | 0 |
| authentication | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| infrastructure | 0 | 1 | 0 | 1 | 2 | 7 | 0 |
| other | 0 | 6 | 0 | 9 | 0 | 3 | 0 |

Examples of mistakes:

- `microsoft__vscode__31728854334` label=compilation predicted=test_assertion - p=0.23
- `microsoft__vscode__31801400244` label=dependency predicted=test_assertion - p=0.26
- `microsoft__vscode__31821965820` label=dependency predicted=other - p=0.23
- `python__cpython__33986657598` label=compilation predicted=test_assertion - p=0.23
- `microsoft__vscode__31954973692` label=compilation predicted=test_assertion - p=0.29
- `microsoft__vscode__31959446031` label=compilation predicted=test_assertion - p=0.33
- `microsoft__vscode__31975340271` label=compilation predicted=test_assertion - p=0.26
- `dotnet__aspire__34767579964` label=dependency predicted=test_assertion - p=0.24
- `microsoft__vscode__34235077561` label=dependency predicted=other - p=0.24
- `microsoft__vscode__34508235056` label=dependency predicted=other - p=0.24

## Method 3 - LLM (OpenRouter)

- Accuracy: **0.71** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.10
- Accuracy when answered: 0.79
- Macro F1: 0.73
- Model: `nvidia/nemotron-3-super-120b-a12b:free`, prompt `v1`
- Tokens per sample: 2307.13 prompt + 347.11 completion; total cost $0.0000
- Median latency: 5.62 s; unparseable replies: 1

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.62 | 1.00 | 0.77 | 5 | 8 |
| test_assertion | 0.93 | 0.82 | 0.87 | 17 | 15 |
| dependency | 0.38 | 0.60 | 0.46 | 5 | 8 |
| authentication | 0.75 | 1.00 | 0.86 | 6 | 8 |
| infrastructure | 1.00 | 0.55 | 0.71 | 11 | 6 |
| other | 0.91 | 0.56 | 0.69 | 18 | 11 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.67 | 0.11 |
| github-actions (targeted-auth) | 7 | 1.00 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| test_assertion | 1 | 14 | 0 | 0 | 0 | 1 | 1 |
| dependency | 1 | 0 | 3 | 1 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 0 | 0 | 0 | 6 | 0 | 5 |
| other | 1 | 1 | 5 | 1 | 0 | 10 | 0 |

Examples of mistakes:

- `microsoft__vscode__31801400244` label=dependency predicted=compilation - conf=0.95 | ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31821965820` label=dependency predicted=authentication - conf=0.95 | npm error [foundry-local] Installation failed: Failed to download Microsoft.AI.Foundry.Local.Core 1.2.3 from any configured feed (api.nuget.org, pkg
- `python__cpython__33789566126` label=test_assertion predicted=compilation - conf=0.95 | IndentationError: unindent does not match any outer indentation level
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - conf=0.95 | ERROR: "eslint" exited with 1.
- `python__cpython__34752783005` label=other predicted=compilation - conf=0.95 | Tools/peg_generator/pegen/c_generator.py:817: error:^[(B Item ^[(B"Group"^[(B of ^[(B"Leaf | Group | Opt | Repeat | Forced | Lookahead | Rhs | Cut"^
- `python__cpython__34746973474` label=infrastructure predicted=unknown - conf=0.20 | Prebuild template deployment failed.
- `python__cpython__34748925258` label=infrastructure predicted=unknown - conf=0.20 | Prebuild template deployment failed.
- `python__cpython__34748927069` label=infrastructure predicted=unknown - conf=0.20 | Prebuild template deployment failed.
- `python__cpython__34756422579` label=infrastructure predicted=unknown - conf=0.20 | Jobs failed, exiting the agent. Job 'ShutdownEnvironment' did not succeed.
- `python__cpython__34758328948` label=infrastructure predicted=unknown - conf=0.20 | Manifest generation failed.

## Method 4 - hybrid (LLM, TF-IDF when the LLM abstains)

- Accuracy: **0.73** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.00
- Accuracy when answered: 0.73
- Macro F1: 0.72
- Runtime: 0.2 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.62 | 1.00 | 0.77 | 5 | 8 |
| test_assertion | 0.94 | 0.88 | 0.91 | 17 | 16 |
| dependency | 0.38 | 0.60 | 0.46 | 5 | 8 |
| authentication | 0.75 | 1.00 | 0.86 | 6 | 8 |
| infrastructure | 1.00 | 0.55 | 0.71 | 11 | 6 |
| other | 0.62 | 0.56 | 0.59 | 18 | 16 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.69 | 0.00 |
| github-actions (targeted-auth) | 7 | 1.00 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| test_assertion | 1 | 15 | 0 | 0 | 0 | 1 | 0 |
| dependency | 1 | 0 | 3 | 1 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 0 | 0 | 0 | 6 | 5 | 0 |
| other | 1 | 1 | 5 | 1 | 0 | 10 | 0 |

Examples of mistakes:

- `microsoft__vscode__31801400244` label=dependency predicted=compilation - conf=0.95 | ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31821965820` label=dependency predicted=authentication - conf=0.95 | npm error [foundry-local] Installation failed: Failed to download Microsoft.AI.Foundry.Local.Core 1.2.3 from any configured feed (api.nuget.org, pkg
- `python__cpython__33789566126` label=test_assertion predicted=compilation - conf=0.95 | IndentationError: unindent does not match any outer indentation level
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - conf=0.95 | ERROR: "eslint" exited with 1.
- `python__cpython__34752783005` label=other predicted=compilation - conf=0.95 | Tools/peg_generator/pegen/c_generator.py:817: error:^[(B Item ^[(B"Group"^[(B of ^[(B"Leaf | Group | Opt | Repeat | Forced | Lookahead | Rhs | Cut"^
- `python__cpython__34746973474` label=infrastructure predicted=other - tfidf fallback p=0.21 (primary: conf=0.20 | Prebuild template deployment failed.)
- `python__cpython__34748925258` label=infrastructure predicted=other - tfidf fallback p=0.21 (primary: conf=0.20 | Prebuild template deployment failed.)
- `python__cpython__34748927069` label=infrastructure predicted=other - tfidf fallback p=0.21 (primary: conf=0.20 | Prebuild template deployment failed.)
- `python__cpython__34756422579` label=infrastructure predicted=other - tfidf fallback p=0.24 (primary: conf=0.20 | Jobs failed, exiting the agent. Job 'ShutdownEnvironment' did not succeed.)
- `python__cpython__34758328948` label=infrastructure predicted=other - tfidf fallback p=0.21 (primary: conf=0.20 | Manifest generation failed.)

## Triage time

No sessions yet. Run `python -m ci_classifier triage --participant <name>` to measure it.
