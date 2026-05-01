"""Unit tests for docling image outcome enum and caption result."""
from app.services.docling import ImageOutcome, CaptionResult, _get_skip_indices


def test_image_outcome_values():
    assert ImageOutcome.CAPTIONED.value == "captioned"
    assert ImageOutcome.SKIPPED_DECORATIVE.value == "skipped_decorative"
    assert ImageOutcome.SKIPPED_TOO_SMALL.value == "skipped_too_small"
    assert ImageOutcome.ERRORED_DECODE.value == "errored_decode"
    assert ImageOutcome.FAILED_UPSTREAM.value == "failed_upstream"


def test_caption_result_action_summary():
    cap = CaptionResult(markdown="", captioned=3, skipped=1, errored=0, failed=2)
    assert cap.action_summary() == "captioning (3 captioned, 1 skipped, 2 failed)"


def test_caption_result_action_summary_with_errored():
    cap = CaptionResult(markdown="", captioned=0, skipped=0, errored=1, failed=0)
    assert cap.action_summary() == "captioning (1 errored)"


def test_get_skip_indices_decorative():
    pictures = [
        {"annotations": [{"label": "logo"}]},
        {"annotations": [{"label": "bar_chart"}]},
        {"annotations": [{"label": "qr_code"}]},
    ]
    skip = _get_skip_indices(pictures)
    assert skip == {0, 2}


def test_get_skip_indices_empty():
    assert _get_skip_indices([]) == set()


def test_get_skip_indices_no_labels():
    pictures = [{"annotations": []}, {"annotations": [{"label": "natural_image"}]}]
    assert _get_skip_indices(pictures) == set()
