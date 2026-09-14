# CI failure classifier evaluation

- Created: 2026-09-14T10:32:53+00:00
- Train / test samples: 653 / 291
- Test labels: authentication=10, compilation=29, dependency=32, infrastructure=21, other=96, test_assertion=103
- labels.jsonl sha256 (first 16): `cd7a7ba744175486`; split created 2026-09-14T10:32:49+00:00

> 284 of 291 test labels are unreviewed drafts (claude-draft).
> Review them with `python -m ci_classifier label --review` before trusting these numbers.

## Baseline 1 - keyword rules

- Accuracy: **0.30** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.54
- Accuracy when answered: 0.65
- Macro F1: 0.37
- Runtime: 0.5 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.62 | 0.34 | 0.44 | 29 | 16 |
| test_assertion | 0.79 | 0.56 | 0.66 | 103 | 73 |
| dependency | 0.33 | 0.38 | 0.35 | 32 | 36 |
| authentication | 1.00 | 0.60 | 0.75 | 10 | 6 |
| infrastructure | 0.00 | 0.00 | 0.00 | 21 | 1 |
| other | 0.00 | 0.00 | 0.00 | 96 | 1 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.31 | 0.60 |
| github-actions (targeted-auth) | 7 | 0.86 | 0.14 |
| logchunks | 229 | 0.28 | 0.54 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 10 | 9 | 1 | 0 | 1 | 0 | 8 |
| test_assertion | 0 | 58 | 12 | 0 | 0 | 1 | 32 |
| dependency | 5 | 1 | 12 | 0 | 0 | 0 | 14 |
| authentication | 0 | 4 | 0 | 6 | 0 | 0 | 0 |
| infrastructure | 0 | 0 | 0 | 0 | 0 | 0 | 21 |
| other | 1 | 1 | 11 | 0 | 0 | 0 | 83 |

Examples of mistakes:

- `logchunks__processone__ejabberd__555702367` label=authentication predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__557756393` label=authentication predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__566947386` label=authentication predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `logchunks__processone__ejabberd__570754006` label=authentication predicted=test_assertion - Testing processone.ejabberd: *** FAILED {ejabberd_SUITE,init_per_group} ***
- `microsoft__vscode__31801400244` label=dependency predicted=compilation - ##[error]src/vs/base/browser/dnd.ts(24,5): error TS2741: Property '_' is missing in type 'Timeout' but required in type 'TimeoutHandle'.
- `microsoft__vscode__31954973692` label=compilation predicted=infrastructure - fatal: unable to access 'https://github.com/microsoft/vscode-smoketest-express/': Could not resolve host: github.com
- `microsoft__vscode__31958099696` label=test_assertion predicted=other - [eslint                   ] Error: eslint failed with 2 warnings and/or errors
- `dotnet__aspire__34767579964` label=dependency predicted=compilation - Build FAILED.
- `python__cpython__34115243281` label=infrastructure predicted=unknown
- `python__cpython__34752783005` label=other predicted=compilation - Tools/peg_generator/pegen/c_generator.py:817: error:^[(B Item ^[(B"Group"^[(B of

## Baseline 2 - TF-IDF + logistic regression

- Accuracy: **0.23** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.73
- Accuracy when answered: 0.82
- Macro F1: 0.16
- Runtime: 1.2 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | - | 0.00 | 0.00 | 29 | 0 |
| test_assertion | 0.92 | 0.23 | 0.37 | 103 | 26 |
| dependency | - | 0.00 | 0.00 | 32 | 0 |
| authentication | 0.00 | 0.00 | 0.00 | 10 | 9 |
| infrastructure | - | 0.00 | 0.00 | 21 | 0 |
| other | 0.93 | 0.44 | 0.60 | 96 | 45 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 55 | 0.11 | 0.75 |
| github-actions (targeted-auth) | 7 | 0.00 | 0.86 |
| logchunks | 229 | 0.26 | 0.72 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 0 | 2 | 0 | 0 | 0 | 0 | 27 |
| test_assertion | 0 | 24 | 0 | 0 | 0 | 0 | 79 |
| dependency | 0 | 0 | 0 | 0 | 0 | 3 | 29 |
| authentication | 0 | 0 | 0 | 0 | 0 | 0 | 10 |
| infrastructure | 0 | 0 | 0 | 1 | 0 | 0 | 20 |
| other | 0 | 0 | 0 | 8 | 0 | 42 | 46 |

Examples of mistakes:

- `logchunks__processone__ejabberd__554568247` label=test_assertion predicted=unknown - p=0.27
- `logchunks__processone__ejabberd__555702367` label=authentication predicted=unknown - p=0.23
- `logchunks__processone__ejabberd__557756393` label=authentication predicted=unknown - p=0.29
- `logchunks__processone__ejabberd__566947386` label=authentication predicted=unknown - p=0.24
- `logchunks__processone__ejabberd__570754006` label=authentication predicted=unknown - p=0.23
- `microsoft__vscode__31728854334` label=compilation predicted=unknown - p=0.23
- `microsoft__vscode__31801400244` label=dependency predicted=unknown - p=0.26
- `microsoft__vscode__31821965820` label=dependency predicted=unknown - p=0.23
- `python__cpython__33986657598` label=compilation predicted=unknown - p=0.23
- `microsoft__vscode__31954973692` label=compilation predicted=unknown - p=0.29

## Triage time

No sessions yet. Run `python -m ci_classifier triage --participant <name>` to measure it.
