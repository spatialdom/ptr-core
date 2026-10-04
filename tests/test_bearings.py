import pytest

from ptr_core import BearingError, parse_bearing
from ptr_core.bearings import is_canonical_bearing


@pytest.mark.parametrize(
    ("value", "azimuth"),
    [
        ("N", 0.0),
        ("E", 90.0),
        ("S", 180.0),
        ("W", 270.0),
        ("N68-28E", 68.46666666666667),
        ("S11-44W", 191.73333333333332),
        ("N68-28-30E", 68.475),
    ],
)
def test_parse_canonical_bearings(value, azimuth):
    bearing = parse_bearing(value)

    assert bearing.canonical == value
    assert bearing.azimuth_degrees == pytest.approx(azimuth)
    assert is_canonical_bearing(value)


@pytest.mark.parametrize(
    ("value", "canonical"),
    [
        ("n68-28e", "N68-28E"),
        ("N 68 28 E", "N68-28E"),
        ("N 68°28' E", "N68-28E"),
        ("N 68 deg 28' E", "N68-28E"),
        ("N68d28m30sE", "N68-28-30E"),
        ("S 11 D 44 M 00 S W", "S11-44W"),
        (" e ", "E"),
    ],
)
def test_normalizes_unambiguous_bearing_input(value, canonical):
    assert parse_bearing(value).canonical == canonical


@pytest.mark.parametrize(
    "value",
    [
        "N068-28E",
        "N68-7E",
        "N68-60E",
        "N68-28-60E",
        "N0-00E",
        "N90-00E",
        "E68-28N",
        "NE68-28",
        "68-28NE",
        "N68E28",
    ],
)
def test_rejects_invalid_or_ambiguous_bearings(value):
    with pytest.raises(BearingError):
        parse_bearing(value)


def test_zero_seconds_normalize_to_omitted_seconds():
    assert parse_bearing("N68-28-00E").canonical == "N68-28E"
    assert not is_canonical_bearing("N68-28-00E")


@pytest.mark.parametrize("word", ["North", "East", "South", "West"])
@pytest.mark.parametrize("prefix", ["", "Due "])
def test_explicit_cardinal_words(word, prefix):
    value = " \t" + (prefix + word).swapcase().replace(" ", " \n ") + "  "
    assert parse_bearing(value).canonical == word[0]
    with pytest.raises(BearingError) as error:
        parse_bearing(value, normalize=False)
    assert error.value.code == "noncanonical_bearing"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("N 45-30 E", "N45-30E"),
        ("N45-30E", "N45-30E"),
        ("N 45\u00b030\u2032 E", "N45-30E"),
        ("N 45\u00b030\u2032 12\u2033 E", "N45-30-12E"),
    ],
)
def test_review_quadrant_examples(value, expected):
    assert parse_bearing(value).canonical == expected


@pytest.mark.parametrize(
    "value", ["DueEast", "Due N", "North East", "Eastward", "90", "Due West 10"]
)
def test_cardinal_allowlist_rejects_guesses(value):
    with pytest.raises(BearingError) as error:
        parse_bearing(value)
    assert error.value.code == "invalid_bearing"


def test_cardinal_aliases_in_mapping_and_tie_line():
    from ptr_core import load_ptr_mapping

    data = {
        "ptr_version": "0.1",
        "lines": [["North", 10], ["Due East", 10], ["South", 10]],
        "tie_point": "Synthetic monument",
        "tie_line": ["Due West", 25],
    }
    record = load_ptr_mapping(data, normalize_bearings=True)
    assert record.tie_line.bearing.canonical == "W"
    assert [c.bearing.canonical for c in record.lines] == ["N", "E", "S"]
    with pytest.raises(ValueError):
        load_ptr_mapping(data)

