# CI failure classifier evaluation

- Created: 2026-09-14T09:19:50+00:00
- Train / test samples: 635 / 279
- Test labels: authentication=6, compilation=29, dependency=36, infrastructure=18, other=92, test_assertion=98
- labels.jsonl sha256 (first 16): `278ae8cd4d76f6d4`; split created 2026-09-14T09:19:48+00:00

> 267 of 279 test labels are unreviewed drafts (claude-draft).
> Review them with `python -m ci_classifier label --review` before trusting these numbers.

## Baseline 1 - keyword rules

- Accuracy: **0.24** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.62
- Accuracy when answered: 0.64
- Macro F1: 0.29
- Runtime: 0.5 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 0.54 | 0.24 | 0.33 | 29 | 13 |
| test_assertion | 0.77 | 0.56 | 0.65 | 98 | 71 |
| dependency | 0.16 | 0.08 | 0.11 | 36 | 19 |
| authentication | 1.00 | 0.50 | 0.67 | 6 | 3 |
| infrastructure | - | 0.00 | 0.00 | 18 | 0 |
| other | - | 0.00 | 0.00 | 92 | 0 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 38 | 0.24 | 0.66 |
| logchunks | 241 | 0.24 | 0.61 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 7 | 3 | 0 | 0 | 0 | 0 | 19 |
| test_assertion | 0 | 55 | 7 | 0 | 0 | 0 | 36 |
| dependency | 5 | 0 | 3 | 0 | 0 | 0 | 28 |
| authentication | 0 | 1 | 0 | 3 | 0 | 0 | 2 |
| infrastructure | 0 | 9 | 0 | 0 | 0 | 0 | 9 |
| other | 1 | 3 | 9 | 0 | 0 | 0 | 79 |

Examples of mistakes:

- `logchunks__iluwatar__java-design-patterns__544453998` label=test_assertion predicted=unknown
- `logchunks__iluwatar__java-design-patterns__564609653` label=dependency predicted=unknown
- `logchunks__iluwatar__java-design-patterns__564623643` label=dependency predicted=unknown
- `logchunks__iluwatar__java-design-patterns__564633185` label=dependency predicted=unknown
- `logchunks__iluwatar__java-design-patterns__565118220` label=dependency predicted=unknown
- `logchunks__iluwatar__java-design-patterns__565203161` label=authentication predicted=unknown
- `logchunks__iluwatar__java-design-patterns__565237143` label=authentication predicted=unknown
- `logchunks__iluwatar__java-design-patterns__565283745` label=authentication predicted=test_assertion - *  External link http://www.amazon.com/Design-Patterns-Elements-Reusable-Object-Oriented/dp/0201633612 failed: got a time out (response code 301)
- `logchunks__iluwatar__java-design-patterns__565304449` label=other predicted=unknown
- `logchunks__iluwatar__java-design-patterns__565659321` label=other predicted=unknown

## Baseline 2 - TF-IDF + logistic regression

- Accuracy: **0.21** (unknown counts as wrong)
- Abstention rate (predicted unknown): 0.77
- Accuracy when answered: 0.91
- Macro F1: 0.16
- Runtime: 1.0 ms/sample

| Category | Precision | Recall | F1 | Support | Predicted |
| --- | --- | --- | --- | --- | --- |
| compilation | 1.00 | 0.03 | 0.07 | 29 | 1 |
| test_assertion | 0.97 | 0.29 | 0.44 | 98 | 29 |
| dependency | - | 0.00 | 0.00 | 36 | 0 |
| authentication | - | 0.00 | 0.00 | 6 | 0 |
| infrastructure | - | 0.00 | 0.00 | 18 | 0 |
| other | 0.86 | 0.33 | 0.47 | 92 | 35 |

By source:

| Source | Samples | Accuracy | Abstention rate |
| --- | --- | --- | --- |
| github-actions | 38 | 0.08 | 0.92 |
| logchunks | 241 | 0.23 | 0.74 |

Confusion matrix (rows = label, columns = prediction):

| label \ predicted | compilation | test_assertion | dependency | authentication | infrastructure | other | unknown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| compilation | 1 | 0 | 0 | 0 | 0 | 2 | 26 |
| test_assertion | 0 | 28 | 0 | 0 | 0 | 0 | 70 |
| dependency | 0 | 0 | 0 | 0 | 0 | 3 | 33 |
| authentication | 0 | 0 | 0 | 0 | 0 | 0 | 6 |
| infrastructure | 0 | 1 | 0 | 0 | 0 | 0 | 17 |
| other | 0 | 0 | 0 | 0 | 0 | 30 | 62 |

Examples of mistakes:

- `logchunks__iluwatar__java-design-patterns__544453998` label=test_assertion predicted=unknown - p=0.33
- `logchunks__iluwatar__java-design-patterns__564609653` label=dependency predicted=unknown - p=0.31
- `logchunks__iluwatar__java-design-patterns__564623643` label=dependency predicted=unknown - p=0.31
- `logchunks__iluwatar__java-design-patterns__564633185` label=dependency predicted=unknown - p=0.27
- `logchunks__iluwatar__java-design-patterns__565118220` label=dependency predicted=unknown - p=0.31
- `logchunks__iluwatar__java-design-patterns__565203161` label=authentication predicted=unknown - p=0.26
- `logchunks__iluwatar__java-design-patterns__565237143` label=authentication predicted=unknown - p=0.26
- `logchunks__iluwatar__java-design-patterns__565283745` label=authentication predicted=unknown - p=0.31
- `logchunks__iluwatar__java-design-patterns__565304449` label=other predicted=unknown - p=0.32
- `logchunks__iluwatar__java-design-patterns__565659321` label=other predicted=unknown - p=0.32

## Triage time

No sessions yet. Run `python -m ci_classifier triage --participant <name>` to measure it.
