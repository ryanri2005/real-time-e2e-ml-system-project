
import csv
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq
import pytest

from a1.data import bronze_ingestion


def _write_csv(
    file_path: Path,
    rows: list[list[str]],
) -> None:
    """Write test records to a CSV file."""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.writer(file)
        writer.writerows(rows)


def _calculate_test_sha256(file_path: Path) -> str:
    """Calculate SHA-256 for synthetic test files."""

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _create_synthetic_project(
    project_root: Path,
) -> None:
    """Create a small synthetic UNSW-NB15 project structure."""

    data_directory = (
        project_root
        / bronze_ingestion.RAW_DATA_RELATIVE_PATH
    )

    data_files = []

    for index, filename in enumerate(
        bronze_ingestion.DATA_FILENAMES,
        start=1,
    ):
        file_path = data_directory / filename

        _write_csv(
            file_path,
            [
                [
                    f"192.0.2.{index}",
                    "",
                    "0",
                ],
                [
                    f"198.51.100.{index}",
                    "0x1F90",
                    "1",
                ],
            ],
        )

        data_files.append(file_path)

    metadata_path = (
        data_directory
        / bronze_ingestion.FEATURE_METADATA_FILENAME
    )

    metadata_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_path.write_text(
        "Synthetic feature metadata for testing.\n",
        encoding="utf-8",
    )

    source_files = [
        *data_files,
        metadata_path,
    ]

    manifest_entries = []

    for file_path in source_files:
        manifest_entries.append(
            {
                "filename": file_path.name,
                "size_bytes": file_path.stat().st_size,
                "sha256": _calculate_test_sha256(file_path),
            }
        )

    source_manifest = {
        "dataset": "UNSW-NB15",
        "generated_at_utc": "2026-01-01T00:00:00+00:00",
        "files": manifest_entries,
    }

    manifest_path = (
        project_root
        / bronze_ingestion.SOURCE_MANIFEST_RELATIVE_PATH
    )

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(
            source_manifest,
            indent=2,
        ),
        encoding="utf-8",
    )


def _mock_feature_metadata(
) -> list[SimpleNamespace]:
    """Provide feature definitions for synthetic CSV files."""

    return [
        SimpleNamespace(
            name="srcip",
            feature_type="nominal",
            description="Synthetic source IP address.",
        ),
        SimpleNamespace(
            name="sport",
            feature_type="integer",
            description="Synthetic source port.",
        ),
        SimpleNamespace(
            name="label",
            feature_type="binary",
            description="Synthetic binary label.",
        ),
    ]


def test_write_csv_to_parquet_preserves_raw_values(
    tmp_path: Path,
) -> None:
    """Verify values, schema, provenance, and row groups."""

    input_path = tmp_path / "synthetic.csv"
    output_path = tmp_path / "synthetic.parquet"

    rows = [
        [
            "192.0.2.1",
            "",
            "0x20205321",
            "service, with comma",
        ],
        [
            "198.51.100.2",
            "  ",
            "-",
            'quoted "value"',
        ],
        [
            "203.0.113.3",
            "443",
            "0",
            "",
        ],
    ]

    _write_csv(
        input_path,
        rows,
    )

    feature_names = [
        "srcip",
        "sport",
        "dsport",
        "service",
    ]

    result = bronze_ingestion._write_csv_to_parquet(
        input_path=input_path,
        output_path=output_path,
        feature_names=feature_names,
        chunk_size=2,
        compression="zstd",
    )

    table = pq.read_table(output_path)

    assert table.num_rows == 3
    assert table.column_names == [
        *feature_names,
        "_source_file",
        "_source_record_number",
    ]

    assert table.schema.field("srcip").type == bronze_ingestion.pa.string()
    assert table.schema.field("sport").type == bronze_ingestion.pa.string()
    assert (
        table.schema.field("_source_record_number").type
        == bronze_ingestion.pa.int64()
    )

    assert table["srcip"].to_pylist() == [
        "192.0.2.1",
        "198.51.100.2",
        "203.0.113.3",
    ]

    assert table["sport"].to_pylist() == [
        "",
        "  ",
        "443",
    ]

    assert table["dsport"].to_pylist() == [
        "0x20205321",
        "-",
        "0",
    ]

    assert table["service"].to_pylist() == [
        "service, with comma",
        'quoted "value"',
        "",
    ]

    assert table["_source_file"].to_pylist() == [
        "synthetic.csv",
        "synthetic.csv",
        "synthetic.csv",
    ]

    assert table["_source_record_number"].to_pylist() == [
        1,
        2,
        3,
    ]

    parquet_file = pq.ParquetFile(output_path)

    assert parquet_file.metadata.num_row_groups == 2

    assert result.record_count == 3
    assert result.row_group_count == 2
    assert result.source_sha256 == _calculate_test_sha256(input_path)
    assert result.output_sha256 == _calculate_test_sha256(output_path)


def test_write_csv_to_parquet_rejects_incorrect_field_count(
    tmp_path: Path,
) -> None:
    """Reject records that do not have the expected number of fields."""

    input_path = tmp_path / "malformed.csv"
    output_path = tmp_path / "malformed.parquet"

    _write_csv(
        input_path,
        [
            ["value1", "value2"],
        ],
    )

    with pytest.raises(
        ValueError,
        match="Incorrect field count",
    ):
        bronze_ingestion._write_csv_to_parquet(
            input_path=input_path,
            output_path=output_path,
            feature_names=["first", "second", "third"],
            chunk_size=2,
            compression="zstd",
        )

    assert not output_path.exists()
    assert not output_path.with_name(
        output_path.name + ".tmp"
    ).exists()


def test_write_csv_to_parquet_rejects_blank_records(
    tmp_path: Path,
) -> None:
    """Reject blank CSV records instead of silently skipping them."""

    input_path = tmp_path / "blank_record.csv"
    output_path = tmp_path / "blank_record.parquet"

    input_path.write_text(
        "value1,value2,value3\n\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Blank CSV record",
    ):
        bronze_ingestion._write_csv_to_parquet(
            input_path=input_path,
            output_path=output_path,
            feature_names=["first", "second", "third"],
            chunk_size=2,
            compression="zstd",
        )

    assert not output_path.exists()
    assert not output_path.with_name(
        output_path.name + ".tmp"
    ).exists()


def test_write_csv_to_parquet_rejects_empty_files(
    tmp_path: Path,
) -> None:
    """Reject an empty CSV file."""

    input_path = tmp_path / "empty.csv"
    output_path = tmp_path / "empty.parquet"

    input_path.write_text(
        "",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="contains no records",
    ):
        bronze_ingestion._write_csv_to_parquet(
            input_path=input_path,
            output_path=output_path,
            feature_names=["first", "second", "third"],
            chunk_size=2,
            compression="zstd",
        )

    assert not output_path.exists()
    assert not output_path.with_name(
        output_path.name + ".tmp"
    ).exists()


def test_ingestion_creates_complete_bronze_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify complete ingestion using synthetic files."""

    _create_synthetic_project(tmp_path)

    monkeypatch.setattr(
        bronze_ingestion,
        "load_feature_metadata",
        lambda _: _mock_feature_metadata(),
    )

    result = bronze_ingestion.ingest_unsw_nb15_bronze(
        project_root=tmp_path,
        chunk_size=1,
        compression="zstd",
    )

    assert result.total_records == 8
    assert len(result.files) == 4
    assert result.output_directory.is_dir()
    assert result.manifest_path.is_file()

    for filename in bronze_ingestion.DATA_FILENAMES:
        parquet_filename = (
            f"{Path(filename).stem}.parquet"
        )

        parquet_path = (
            result.output_directory / parquet_filename
        )

        assert parquet_path.is_file()

        table = pq.read_table(parquet_path)

        assert table.num_rows == 2

        assert table["sport"].to_pylist() == [
            "",
            "0x1F90",
        ]

        assert table["label"].to_pylist() == [
            "0",
            "1",
        ]

        assert table["_source_file"].to_pylist() == [
            filename,
            filename,
        ]

        assert table["_source_record_number"].to_pylist() == [
            1,
            2,
        ]

    manifest = json.loads(
        result.manifest_path.read_text(
            encoding="utf-8"
        )
    )

    assert manifest["dataset"] == "UNSW-NB15"
    assert manifest["layer"] == "bronze"
    assert manifest["total_records"] == 8
    assert manifest["chunk_size_rows"] == 1
    assert manifest["compression"] == "zstd"

    assert manifest["source_manifest_generated_at_utc"] == (
        "2026-01-01T00:00:00+00:00"
    )

    assert len(manifest["source_files"]) == 5
    assert len(manifest["feature_schema"]) == 3
    assert len(manifest["files"]) == 4

    assert not list(
        result.output_directory.parent.glob(
            ".bronze-staging-*"
        )
    )

    with pytest.raises(FileExistsError):
        bronze_ingestion.ingest_unsw_nb15_bronze(
            project_root=tmp_path,
            chunk_size=1,
            compression="zstd",
        )


def test_ingestion_rejects_source_hash_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject a source file with a changed hash but unchanged size."""

    _create_synthetic_project(tmp_path)

    changed_file = (
        tmp_path
        / bronze_ingestion.RAW_DATA_RELATIVE_PATH
        / bronze_ingestion.DATA_FILENAMES[0]
    )

    original_contents = changed_file.read_bytes()

    changed_contents = original_contents.replace(
        b"192.0.2.1",
        b"192.0.2.9",
        1,
    )

    assert changed_contents != original_contents
    assert len(changed_contents) == len(original_contents)

    changed_file.write_bytes(changed_contents)

    monkeypatch.setattr(
        bronze_ingestion,
        "load_feature_metadata",
        lambda _: _mock_feature_metadata(),
    )

    with pytest.raises(
        ValueError,
        match="SHA-256 mismatch",
    ):
        bronze_ingestion.ingest_unsw_nb15_bronze(
            project_root=tmp_path,
            chunk_size=1,
            compression="zstd",
        )

    output_directory = (
        tmp_path / bronze_ingestion.BRONZE_OUTPUT_RELATIVE_PATH
    )

    assert not output_directory.exists()
