import pandas as pd
import pytest

from a1.data.csv_validation import (
    validate_csv_structure,
)
from a1.data.schema import (
    load_feature_metadata,
    load_feature_names,
)


def test_csv_structure_counts_valid_and_malformed_records(
    tmp_path,
) -> None:
    """Check record counts, field counts, and blank-line handling."""

    csv_path = tmp_path / "sample.csv"

    csv_path.write_text(
        "first,second,third\n"
        '"four,five",six,seven\n'
        "\n"
        "short,row\n",
        encoding="utf-8",
    )

    report = validate_csv_structure(
        file_path=csv_path,
        expected_columns=3,
    )

    assert report.data_records == 3
    assert report.blank_records == 1
    assert report.valid_records == 2
    assert report.malformed_records == 1
    assert report.is_valid is False

    assert len(report.malformed_examples) == 1

    example = report.malformed_examples[0]

    assert example.record_number == 3
    assert example.physical_line_number == 4
    assert example.observed_field_count == 2


def test_csv_structure_rejects_empty_file(
    tmp_path,
) -> None:
    """An empty CSV must not pass structural validation."""

    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    report = validate_csv_structure(
        file_path=csv_path,
        expected_columns=49,
    )

    assert report.data_records == 0
    assert report.blank_records == 0
    assert report.valid_records == 0
    assert report.malformed_records == 0
    assert report.is_valid is False


def test_csv_structure_rejects_malformed_csv_quoting(
    tmp_path,
) -> None:
    """Invalid CSV quoting should produce an understandable error."""

    csv_path = tmp_path / "invalid.csv"

    csv_path.write_text(
        '"unterminated,field\n',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="CSV parsing failed",
    ):
        validate_csv_structure(
            file_path=csv_path,
            expected_columns=2,
        )


def test_feature_names_and_types_are_normalized(
    tmp_path,
) -> None:
    """Metadata names and feature types should be normalized."""

    metadata_path = tmp_path / "features.csv"

    names = []

    for index in range(44):
        names.append(f"feature_{index}")

    names.extend([
        "Label",
        "Attack_cat",
        "Stime",
        "Ltime",
        "CT_src_ ltm",
    ])

    feature_types = ["integer"] * 44

    feature_types.extend([
        "binary",
        "nominal",
        "timestamp",
        "timestamp",
        "integer",
    ])

    metadata = pd.DataFrame({
        "Name": names,
        "Type": feature_types,
        "Description": ["test"] * len(names),
    })

    metadata.to_csv(
        metadata_path,
        index=False,
        encoding="cp1252",
    )

    feature_definitions = load_feature_metadata(
        metadata_path
    )

    feature_names = load_feature_names(metadata_path)

    assert len(feature_definitions) == 49
    assert len(feature_names) == 49
    assert len(set(feature_names)) == 49

    assert "label" in feature_names
    assert "attack_cat" in feature_names
    assert "stime" in feature_names
    assert "ltime" in feature_names
    assert "ct_src_ltm" in feature_names

    feature_lookup = {
        feature.name: feature
        for feature in feature_definitions
    }

    assert feature_lookup["label"].feature_type == "binary"
    assert feature_lookup["attack_cat"].feature_type == "nominal"
    assert feature_lookup["stime"].feature_type == "timestamp"
    assert feature_lookup["ct_src_ltm"].feature_type == "integer"