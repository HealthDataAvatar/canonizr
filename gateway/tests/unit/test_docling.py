"""Unit tests for image post-processing: outcome enum, caption result, skip indices."""
from app.services.image_postprocess import ImageOutcome, _get_skip_indices


def test_image_outcome_values():
    assert ImageOutcome.CAPTIONED.value == "captioned"
    assert ImageOutcome.SKIPPED_DECORATIVE.value == "skipped_decorative"
    assert ImageOutcome.SKIPPED_TOO_SMALL.value == "skipped_too_small"
    assert ImageOutcome.ERRORED_DECODE.value == "errored_decode"
    assert ImageOutcome.LABELLED.value == "labelled"



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
