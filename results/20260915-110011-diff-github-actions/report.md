# CI failure classifier evaluation

- Created: 2026-09-15T04:00:11+00:00
- Train / test samples: 653 / 62
- Excerpt profile: `diff`; test samples from source: `github-actions`
- Test labels: authentication=6, compilation=5, dependency=5, infrastructure=10, other=18, test_assertion=18
- labels.jsonl sha256 (first 16): `13813d6217e55d27`; split created 2026-09-14T10:32:49+00:00

## Uncertainty and significance

95% confidence intervals from a cluster bootstrap (1000 resamples of whole
repo/workflow groups, since runs of one workflow are not independent):

| Method | Samples | Accuracy [95% CI] | Macro F1 [95% CI] |
| --- | --- | --- | --- |
| rules | 62 | 0.37 [0.15, 0.62] | 0.52 [0.27, 0.60] |
| tfidf | 62 | 0.03 [0.00, 0.10] | 0.03 [0.00, 0.12] |
| llm | 62 | 0.74 [0.56, 0.88] | 0.70 [0.51, 0.83] |

Exact McNemar test on the samples both methods scored (p < 0.05: the accuracy difference is unlikely to be chance;
samples are treated as independent here, so read borderline p-values with care):

| A vs B | Samples | Only A right | Only B right | p-value |
| --- | --- | --- | --- | --- |
| rules vs tfidf | 62 | 21 | 0 | 9.5e-07 |
| rules vs llm | 62 | 3 | 26 | 1.5e-05 |
| tfidf vs llm | 62 | 0 | 44 | 1.1e-13 |

## Cross-validation

Grouped, stratified 5-fold cross-validation over all 194 labelled samples (whole repo/workflow
groups per fold; TF-IDF refitted on the other folds). Per-fold values are in `cv_folds.csv`.

| Method | Folds | Samples scored | Accuracy (mean ± sd) | Macro F1 (mean ± sd) | Abstention (mean) |
| --- | --- | --- | --- | --- | --- |
| rules | 5 | 194 | 0.30 ± 0.14 | 0.37 ± 0.14 | 0.53 |
| tfidf | 5 | 194 | 0.03 ± 0.04 | 0.05 ± 0.08 | 0.95 |
| llm | 4 | 62 | 0.55 ± 0.40 | 0.49 ± 0.38 | 0.18 |

> llm is scored only on the 62 samples that already have stored answers (`llm-run`).

## Baseline 1 - keyword rules

- Accuracy: **0.37** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.55
- Accuracy when answered: 0.82
- Macro F1: 0.52
- Runtime: 0.9 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.57 | 0.80 | 0.67 | 5 | 7 |
| test_assertion | 1.00 | 0.56 | 0.71 | 18 | 10 |
| dependency | 1.00 | 0.60 | 0.75 | 5 | 3 |
| authentication | 1.00 | 1.00 | 1.00 | 6 | 6 |
| infrastructure | 0.00 | 0.00 | 0.00 | 10 | 1 |
| other | 0.00 | 0.00 | 0.00 | 18 | 1 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.31 | 0.60 |
| github-actions (targeted-auth) | 7 | 0.86 | 0.14 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 4 | 0 | 0 | 0 | 1 | 0 | 0 |
| test_assertion | 0 | 10 | 0 | 0 | 0 | 1 | 7 |
| dependency | 2 | 0 | 3 | 0 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 0 | 0 | 0 | 0 | 0 | 10 |
| other | 1 | 0 | 0 | 0 | 0 | 0 | 17 |

Examples of mistakes:

- `microsoft__vscode__31801400244` label=dependency predicted=compilation - ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31954973692` label=compilation predicted=infrastructure - fatal: unable to access 'https://github.com/microsoft/vscode-smoketest-express/': Could not resolve host: github.com
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - [eslint                   ] Error: eslint failed with 2 warnings and/or errors
- `dotnet__aspire__34767579964` label=dependency predicted=compilation - Build FAILED.
- `python__cpython__34115243281` label=infrastructure predicted=unknown
- `python__cpython__34752783005` label=other predicted=compilation - Tools/peg_generator/pegen/c_generator.py:817: error:^[(B Item ^[(B"Group"^[(B of
- `microsoft__vscode__31790622084` label=infrastructure predicted=unknown
- `microsoft__TypeScript__32991948166` label=infrastructure predicted=unknown
- `hashicorp__terraform-provider-aws__34274218483` label=infrastructure predicted=unknown
- `python__cpython__34746973250` label=infrastructure predicted=unknown

## Baseline 2 - TF-IDF + logistic regression

- Accuracy: **0.03** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.94
- Accuracy when answered: 0.50
- Macro F1: 0.03
- Runtime: 1.5 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | - | 0.00 | 0.00 | 5 | 0 |
| test_assertion | 1.00 | 0.11 | 0.20 | 18 | 2 |
| dependency | - | 0.00 | 0.00 | 5 | 0 |
| authentication | 0.00 | 0.00 | 0.00 | 6 | 2 |
| infrastructure | - | 0.00 | 0.00 | 10 | 0 |
| other | - | 0.00 | 0.00 | 18 | 0 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.04 | 0.93 |
| github-actions (targeted-auth) | 7 | 0.00 | 1.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| test_assertion | 0 | 2 | 0 | 0 | 0 | 0 | 16 |
| dependency | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| authentication | 0 | 0 | 0 | 0 | 0 | 0 | 6 |
| infrastructure | 0 | 0 | 0 | 0 | 0 | 0 | 10 |
| other | 0 | 0 | 0 | 2 | 0 | 0 | 16 |

Examples of mistakes:

- `microsoft__vscode__31728854334` label=compilation predicted=unknown - p=0.27
- `microsoft__vscode__31801400244` label=dependency predicted=unknown - p=0.25
- `microsoft__vscode__31821965820` label=dependency predicted=unknown - p=0.24
- `python__cpython__33789566126` label=test_assertion predicted=unknown - p=0.34
- `python__cpython__33986657598` label=compilation predicted=unknown - p=0.27
- `python__cpython__34490228347` label=test_assertion predicted=unknown - p=0.33
- `python__cpython__34698360815` label=test_assertion predicted=unknown - p=0.38
- `microsoft__vscode__31954973692` label=compilation predicted=unknown - p=0.24
- `microsoft__vscode__31958099696` label=test_assertion predicted=unknown - p=0.22
- `microsoft__vscode__31959446031` label=compilation predicted=unknown - p=0.29

## Method 3 - LLM (OpenRouter)

- Accuracy: **0.74** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.06
- Accuracy when answered: 0.79
- Macro F1: 0.70
- Model: `nvidia/nemotron-3-super-120b-a12b:free`, prompt `v1`
- Tokens per sample: 2440.66 prompt + 340.02 completion; total cost $0.0000
- Median latency: 4.42 s; unparseable replies: 1

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.56 | 1.00 | 0.71 | 5 | 9 |
| test_assertion | 1.00 | 0.89 | 0.94 | 18 | 16 |
| dependency | 0.33 | 0.40 | 0.36 | 5 | 6 |
| authentication | 0.67 | 1.00 | 0.80 | 6 | 9 |
| infrastructure | 1.00 | 0.40 | 0.57 | 10 | 4 |
| other | 0.93 | 0.72 | 0.81 | 18 | 14 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.71 | 0.07 |
| github-actions (targeted-auth) | 7 | 1.00 | 0.00 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| test_assertion | 1 | 16 | 0 | 0 | 0 | 0 | 1 |
| dependency | 2 | 0 | 2 | 1 | 0 | 0 | 0 |
| authentication | 0 | 0 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 0 | 2 | 0 | 4 | 1 | 3 |
| other | 1 | 0 | 2 | 2 | 0 | 13 | 0 |

Examples of mistakes:

- `microsoft__vscode__31801400244` label=dependency predicted=compilation - conf=0.99 | ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31821965820` label=dependency predicted=authentication - conf=0.95 | npm error [foundry-local] Installation failed: Failed to download Microsoft.AI.Foundry.Local.Core 1.2.3 from any configured feed (api.nuget.org, pkg
- `python__cpython__33789566126` label=test_assertion predicted=compilation - conf=0.95 | IndentationError: unindent does not match any outer indentation level
- `dotnet__aspire__34767579964` label=dependency predicted=compilation - conf=0.95 | D:\a\aspire\aspire\tests\Aspire.Hosting.RemoteHost.Tests\Aspire.Hosting.RemoteHost.Tests.csproj : error NU3027: Warning As Error: Package 'Microsoft
- `python__cpython__34752783005` label=other predicted=compilation - conf=0.95 | Tools/peg_generator/pegen/c_generator.py:817: error:^[(B Item ^[(B"Group"^[(B of ^[(B"Leaf | Group | Opt | Repeat | Forced | Lookahead | Rhs | Cut"^
- `microsoft__vscode__31790622084` label=infrastructure predicted=dependency - conf=0.90 | [cca-engine] turn=23 session.error: Execution failed: CAPIError: 400 Error while downloading file. Upstream status code: 404. (Request ID: 4000:11A5
- `microsoft__TypeScript__32991948166` label=infrastructure predicted=dependency - conf=0.95 | go: github.com/aws/aws-sdk-go-v2/service/ssooidc@v1.35.16: read "https://proxy.golang.org/github.com/aws/aws-sdk-go-v2/service/ssooidc/@v/v1.35.16.z
- `python__cpython__34746973250` label=infrastructure predicted=unknown - conf=0.20 | Prebuild template deployment failed.
- `python__cpython__34746973474` label=infrastructure predicted=unknown - conf=0.20 | Prebuild template deployment failed.
- `python__cpython__34748927069` label=infrastructure predicted=unknown - conf=0.20 | Prebuild template deployment failed.

## Triage time

No sessions yet. Run `python -m ci_classifier triage --participant <name>` to measure it.
