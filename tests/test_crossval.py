from ci_classifier import crossval, llm

CONFIG = {
    "categories": ["compilation", "dependency", "other"],
    "tfidf": {"abstain_below": 0.0},
    "llm": {"model": "test/model:free", "abstain_below": 0.0},
}
TEXTS = {
    "compilation": "src/app.cs(3,1): error CS1002: ; expected\nBuild FAILED.",
    "dependency": "npm ERR! code ERESOLVE unable to resolve dependency tree",
    "other": "Code style issues found in 3 files. Run Prettier with --write to fix.",
}


def make_data(n_groups=10):
    labels, manifest, excerpts = {}, {}, {}
    for g in range(n_groups):
        for label in TEXTS:
            for r in range(2):
                sid = f"g{g}-{label}-{r}"
                labels[sid] = {"label": label}
                manifest[sid] = {"repo": f"org/repo{g}", "workflow": f"wf-{label}"}
                excerpts[sid] = f"{TEXTS[label]}\nrun {g}-{r}"
    return labels, manifest, excerpts


def test_cross_validate_covers_every_sample_once_and_keeps_groups(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "PREDICTIONS", tmp_path / "none.jsonl")
    labels, manifest, excerpts = make_data()
    folds = crossval.cross_validate(list(labels), labels, manifest, CONFIG, folds=5, seed=1, excerpts=excerpts)

    rules_rows = folds[folds["method"] == "rules"]
    assert rules_rows["test_samples"].sum() == len(labels)
    assert set(folds["method"]) == {"rules", "tfidf"}          # no stored LLM answers -> LLM not scored
    assert (folds.loc[folds["method"] == "tfidf", "accuracy"] == 1.0).all()

    summary = crossval.summarize(folds)
    assert summary.loc["rules", "folds"] == 5
    assert summary.loc["rules", "scored"] == len(labels)
