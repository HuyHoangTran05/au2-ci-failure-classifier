import json

from ci_classifier import crossval, llm
from ci_classifier.common import UNKNOWN
from ci_classifier.methods import METHODS, with_fallback


def test_fallback_answers_only_when_primary_abstains():
    primary = {"a": ("compilation", "conf=0.9"), "b": (UNKNOWN, "conf=0.3"), "c": None}.get
    fallback = lambda text: ("dependency", "p=0.55")
    predict = with_fallback(primary, fallback)

    assert predict("a") == ("compilation", "conf=0.9")
    assert predict("b") == ("dependency", "tfidf fallback p=0.55 (primary: conf=0.3)")
    assert predict("c") is None          # no stored LLM answer: stays unanswered, not filled by the fallback


def test_fallback_keeps_primary_when_fallback_has_no_answer():
    predict = with_fallback(lambda text: (UNKNOWN, ""), lambda text: None)
    assert predict("x") == (UNKNOWN, "")


def test_hybrid_is_a_method():
    assert "hybrid" in METHODS


def test_cross_validation_scores_hybrid_on_llm_answered_samples(tmp_path, monkeypatch):
    from test_crossval import CONFIG, make_data

    labels, manifest, excerpts = make_data()
    stored = tmp_path / "predictions.jsonl"
    # The LLM answered every "dependency" sample, always with "unknown"; nothing else was sent to the API.
    stored.write_text("".join(
        json.dumps({"model": CONFIG["llm"]["model"], "prompt_version": llm.PROMPT_VERSION,
                    "excerpt_sha": llm.excerpt_sha(text), "category": UNKNOWN, "evidence": "", "confidence": None}) + "\n"
        for sid, text in excerpts.items() if labels[sid]["label"] == "dependency"), encoding="utf-8")
    monkeypatch.setattr(llm, "PREDICTIONS", stored)

    folds = crossval.cross_validate(list(labels), labels, manifest, CONFIG, folds=5, seed=1, excerpts=excerpts)
    summary = crossval.summarize(folds)
    answered = sum(labels[sid]["label"] == "dependency" for sid in labels)
    assert summary.loc["llm", "scored"] == summary.loc["hybrid", "scored"] == answered
    assert (folds.loc[folds["method"] == "llm", "accuracy"] == 0.0).all()
    assert (folds.loc[folds["method"] == "hybrid", "accuracy"] == 1.0).all()   # TF-IDF fills every abstention
