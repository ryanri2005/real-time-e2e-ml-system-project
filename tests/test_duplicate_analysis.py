import csv

import pytest

from a1.data import duplicate_analysis
from a1.data.duplicate_analysis import (
    analyze_duplicates,
)


def test_duplicate_analysis_detects_within_and_cross_file_duplicates(
    tmp_path,
) -> None:
    """Verify exact duplicate groups and source locations."""

    data_directory = tmp_path / "raw"
    output_directory = tmp_path / "reports"

    data_directory.mkdir()

    first_file = data_directory / "one.csv"
    second_file = data_directory / "two.csv"

    first_file.write_text(
        "a,b,c\n"
        '"hello,world",x,y\n'
        "a,b,c\n",
        encoding="utf-8",
    )

    second_file.write_text(
        "a,b,c\n"
        '"hello,world",x,y\n',
        encoding="utf-8",
    )

    report = analyze_duplicates(
        data_directory=data_directory,
        output_directory=output_directory,
        expected_columns=3,
        data_filenames=("one.csv", "two.csv"),
        batch_size=2,
    )

    assert report["total_records"] == 5

    assert report["unique_records"] == 2

    assert report["duplicate_groups"] == 2

    assert report["records_in_duplicate_groups"] == 5

    assert report["duplicate_excess_records"] == 3

    assert report["same_file_duplicate_groups"] == 1

    assert report["cross_file_duplicate_groups"] == 2

    assert report["same_file_extra_occurrences"] == 1

    assert report["duplicate_occurrence_locations"] == 5

    group_path = (
        output_directory
        / "unsw_nb15_duplicate_groups.csv"
    )

    with group_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        groups = list(csv.DictReader(file))

    assert len(groups) == 2

    assert int(groups[0]["occurrences"]) == 3

    assert groups[0]["first_file"] == "one.csv"

    assert int(groups[0]["first_record_number"]) == 1

    assert int(groups[0]["records_in_one.csv"]) == 2

    assert int(groups[0]["records_in_two.csv"]) == 1

    occurrence_path = (
        output_directory
        / "unsw_nb15_duplicate_occurrences.csv"
    )

    with occurrence_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        occurrences = list(csv.DictReader(file))

    assert len(occurrences) == 5

    locations = {
        (
            row["filename"],
            int(row["record_number"]),
        )
        for row in occurrences
    }

    assert locations == {
        ("one.csv", 1),
        ("one.csv", 2),
        ("one.csv", 3),
        ("two.csv", 1),
        ("two.csv", 2),
    }


def test_duplicate_analysis_handles_dataset_without_duplicates(
    tmp_path,
) -> None:
    """Verify correct output when all records are unique."""

    data_directory = tmp_path / "raw"
    output_directory = tmp_path / "reports"

    data_directory.mkdir()

    csv_path = data_directory / "unique.csv"

    csv_path.write_text(
        "a,b,c\n"
        "d,e,f\n",
        encoding="utf-8",
    )

    report = analyze_duplicates(
        data_directory=data_directory,
        output_directory=output_directory,
        expected_columns=3,
        data_filenames=("unique.csv",),
    )

    assert report["total_records"] == 2

    assert report["unique_records"] == 2

    assert report["duplicate_groups"] == 0

    assert report["duplicate_excess_records"] == 0

    assert report["duplicate_occurrence_locations"] == 0

    group_path = (
        output_directory
        / "unsw_nb15_duplicate_groups.csv"
    )

    with group_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        assert len(list(csv.reader(file))) == 1


def test_duplicate_analysis_rejects_malformed_record(
    tmp_path,
) -> None:
    """Reject records with the wrong number of fields."""

    data_directory = tmp_path / "raw"
    output_directory = tmp_path / "reports"

    data_directory.mkdir()

    csv_path = data_directory / "malformed.csv"

    csv_path.write_text(
        "a,b,c\n"
        "d,e\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unexpected field count",
    ):

        analyze_duplicates(
            data_directory=data_directory,
            output_directory=output_directory,
            expected_columns=3,
            data_filenames=("malformed.csv",),
        )


def test_duplicate_analysis_detects_hash_collisions(
    tmp_path,
    monkeypatch,
) -> None:
    """Different records must never be classified as duplicates solely by hash."""

    data_directory = tmp_path / "raw"
    output_directory = tmp_path / "reports"

    data_directory.mkdir()

    csv_path = data_directory / "collision.csv"

    csv_path.write_text(
        "a,b\n"
        "x,y\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        duplicate_analysis,
        "_hash_record",
        lambda payload: b"x" * 32,
    )

    with pytest.raises(
        RuntimeError,
        match="SHA-256 collision",
    ):

        analyze_duplicates(
            data_directory=data_directory,
            output_directory=output_directory,
            expected_columns=2,
            data_filenames=("collision.csv",),
            batch_size=1,
        )