
import argparse
import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from a1.data.bronze_ingestion import (
    BRONZE_OUTPUT_RELATIVE_PATH,
    calculate_sha256,
    verify_source_manifest,
)
from a1.data.schema import (
    DATA_FILENAMES,
    FEATURE_METADATA_FILENAME,
    RAW_DATA_RELATIVE_PATH,
    find_project_root,
    load_feature_metadata,
)

DEFAULT_BATCH_SIZE = 10_000


def verify_bronze_file(
    project_root: Path,
    output_directory: Path,
    filename: str,
    file_manifest: dict,
    feature_names: list[str],
    compression: str,
    batch_size: int,
) -> dict:
    """Compare every Parquet value against its original CSV value."""

    input_path = (
        project_root
        / RAW_DATA_RELATIVE_PATH
        / filename
    )

    parquet_filename = (
        f"{Path(filename).stem}.parquet"
    )

    parquet_path = (
        output_directory / parquet_filename
    )

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Original CSV not found: {input_path}"
        )

    if not parquet_path.is_file():
        raise FileNotFoundError(
            f"Bronze Parquet file not found: {parquet_path}"
        )

    if file_manifest.get("source_filename") != filename:
        raise ValueError(
            f"Manifest source filename mismatch for {filename}."
        )

    if file_manifest.get("parquet_filename") != parquet_filename:
        raise ValueError(
            f"Manifest Parquet filename mismatch for {filename}."
        )

    actual_source_hash = calculate_sha256(input_path)

    if (
        actual_source_hash.lower()
        != file_manifest.get("source_sha256", "").lower()
    ):
        raise ValueError(
            f"Source checksum mismatch for {filename}."
        )

    actual_output_hash = calculate_sha256(parquet_path)

    if (
        actual_output_hash.lower()
        != file_manifest.get("output_sha256", "").lower()
    ):
        raise ValueError(
            f"Parquet checksum mismatch for {parquet_filename}."
        )

    actual_output_size = parquet_path.stat().st_size

    if actual_output_size != file_manifest.get("output_size_bytes"):
        raise ValueError(
            f"Parquet file size mismatch for {parquet_filename}."
        )

    parquet_file = pq.ParquetFile(parquet_path)
    metadata = parquet_file.metadata

    expected_column_names = [
        *feature_names,
        "_source_file",
        "_source_record_number",
    ]

    actual_schema = parquet_file.schema_arrow

    expected_fields = [
        (name, pa.string())
        for name in feature_names
    ]

    expected_fields.extend(
        [
            ("_source_file", pa.string()),
            ("_source_record_number", pa.int64()),
        ]
    )

    actual_fields = [
        (field.name, field.type)
        for field in actual_schema
    ]

    if actual_fields != expected_fields:
        raise ValueError(
            f"Parquet schema mismatch for {parquet_filename}."
        )

    if actual_schema.names != expected_column_names:
        raise ValueError(
            f"Parquet column order mismatch for {parquet_filename}."
        )

    expected_record_count = file_manifest.get("record_count")

    if not isinstance(expected_record_count, int):
        raise TypeError(
            f"Invalid record count in manifest for {filename}."
        )

    if metadata.num_rows != expected_record_count:
        raise ValueError(
            f"Parquet row count mismatch for {parquet_filename}: "
            f"manifest says {expected_record_count:,}, "
            f"Parquet contains {metadata.num_rows:,}."
        )

    expected_row_groups = (
        expected_record_count + batch_size - 1
    ) // batch_size

    # The original ingestion chunk size determines the row groups.
    # Verification batch size is independent of that setting.
    expected_ingestion_chunk_size = file_manifest.get(
        "ingestion_chunk_size_rows"
    )

    if expected_ingestion_chunk_size is None:
        raise ValueError(
            "Missing ingestion chunk size in file manifest."
        )

    expected_row_groups = (
        expected_record_count
        + expected_ingestion_chunk_size
        - 1
    ) // expected_ingestion_chunk_size

    if metadata.num_row_groups != expected_row_groups:
        raise ValueError(
            f"Row-group count mismatch for {parquet_filename}: "
            f"expected {expected_row_groups}, "
            f"found {metadata.num_row_groups}."
        )

    expected_compression = compression.upper()

    for row_group_index in range(metadata.num_row_groups):
        row_group = metadata.row_group(row_group_index)

        for column_index in range(len(expected_column_names)):
            column = row_group.column(column_index)

            if column.compression.upper() != expected_compression:
                raise ValueError(
                    f"Compression mismatch in {parquet_filename}, "
                    f"row group {row_group_index}, "
                    f"column {column_index}: "
                    f"expected {expected_compression}, "
                    f"found {column.compression}."
                )

    records_checked = 0
    feature_count = len(feature_names)

    with input_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as source_file:

        reader = csv.reader(
            source_file,
            strict=True,
        )

        try:
            for batch in parquet_file.iter_batches(
                batch_size=batch_size
            ):
                batch_rows = batch.num_rows

                expected_columns = [
                    []
                    for _ in feature_names
                ]

                for batch_offset in range(batch_rows):
                    try:
                        source_row = next(reader)
                    except StopIteration as error:
                        raise ValueError(
                            f"Original CSV ended early in {filename} "
                            f"at record {records_checked + 1}."
                        ) from error

                    if not source_row:
                        raise ValueError(
                            f"Blank CSV record in {filename} "
                            f"at record {records_checked + 1}."
                        )

                    if len(source_row) != feature_count:
                        raise ValueError(
                            f"Incorrect field count in {filename} "
                            f"at record {records_checked + 1}: "
                            f"expected {feature_count}, "
                            f"found {len(source_row)}."
                        )

                    for column_index, value in enumerate(source_row):
                        expected_columns[column_index].append(value)

                for column_index, feature_name in enumerate(
                    feature_names
                ):
                    actual_values = (
                        batch.column(column_index).to_pylist()
                    )

                    expected_values = expected_columns[column_index]

                    if actual_values != expected_values:
                        for row_offset, (
                            actual_value,
                            expected_value,
                        ) in enumerate(
                            zip(
                                actual_values,
                                expected_values,
                                strict=True,
                            )
                        ):
                            if actual_value != expected_value:
                                record_number = (
                                    records_checked
                                    + row_offset
                                    + 1
                                )

                                raise ValueError(
                                    f"Value mismatch in {filename}, "
                                    f"record {record_number}, "
                                    f"feature {feature_name}: "
                                    f"CSV={expected_value!r}, "
                                    f"Parquet={actual_value!r}."
                                )

                actual_source_files = (
                    batch.column(feature_count).to_pylist()
                )

                expected_source_files = [
                    filename
                    for _ in range(batch_rows)
                ]

                if actual_source_files != expected_source_files:
                    raise ValueError(
                        f"Source filename provenance mismatch "
                        f"in {parquet_filename}."
                    )

                actual_record_numbers = (
                    batch.column(feature_count + 1).to_pylist()
                )

                expected_record_numbers = list(
                    range(
                        records_checked + 1,
                        records_checked + batch_rows + 1,
                    )
                )

                if actual_record_numbers != expected_record_numbers:
                    raise ValueError(
                        f"Record-number provenance mismatch "
                        f"in {parquet_filename}."
                    )

                records_checked += batch_rows

        except csv.Error as error:
            raise ValueError(
                f"CSV parsing error while verifying {filename}: {error}"
            ) from error

        extra_row = next(reader, None)

        if extra_row is not None:
            raise ValueError(
                f"Original CSV contains additional records "
                f"after Parquet data ended: {filename}."
            )

    if records_checked != expected_record_count:
        raise ValueError(
            f"Final verified record count mismatch for {filename}: "
            f"expected {expected_record_count:,}, "
            f"verified {records_checked:,}."
        )

    return {
        "source_filename": filename,
        "parquet_filename": parquet_filename,
        "records_verified": records_checked,
        "row_groups": metadata.num_row_groups,
        "output_size_bytes": actual_output_size,
        "output_sha256": actual_output_hash,
    }


def verify_bronze_dataset(
    project_root: Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[dict]:
    """Independently verify the complete Bronze dataset."""

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than zero."
        )

    if project_root is None:
        project_root = find_project_root()

    project_root = project_root.resolve()

    output_directory = (
        project_root / BRONZE_OUTPUT_RELATIVE_PATH
    )

    if not output_directory.is_dir():
        raise FileNotFoundError(
            f"Bronze output directory not found: {output_directory}"
        )

    manifest_path = (
        output_directory / "ingestion_manifest.json"
    )

    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Bronze ingestion manifest not found: {manifest_path}"
        )

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        manifest = json.load(file)

    if not isinstance(manifest, dict):
        raise TypeError(
            "Bronze manifest must contain a JSON object."
        )

    if manifest.get("dataset") != "UNSW-NB15":
        raise ValueError(
            "Bronze manifest does not describe UNSW-NB15."
        )

    if manifest.get("layer") != "bronze":
        raise ValueError(
            "Manifest layer must be bronze."
        )

    chunk_size = manifest.get("chunk_size_rows")

    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size <= 0
    ):
        raise ValueError(
            "Invalid ingestion chunk size in Bronze manifest."
        )

    compression = manifest.get("compression")

    if not isinstance(compression, str):
        raise TypeError(
            "Compression setting is missing from Bronze manifest."
        )

    verified_sources = verify_source_manifest(
        project_root
    )

    source_entries = manifest.get("source_files")

    if not isinstance(source_entries, list):
        raise TypeError(
            "Bronze manifest must contain a source_files list."
        )

    source_entries_by_name = {}

    for entry in source_entries:
        if not isinstance(entry, dict):
            raise TypeError(
                "Every source file entry must be a JSON object."
            )

        filename = entry.get("filename")

        if not isinstance(filename, str):
            raise TypeError(
                "A source file entry has no valid filename."
            )

        if filename in source_entries_by_name:
            raise ValueError(
                f"Duplicate source file entry: {filename}"
            )

        source_entries_by_name[filename] = entry

    for filename, verified in verified_sources.items():
        entry = source_entries_by_name.get(filename)

        if entry is None:
            raise ValueError(
                f"Source file missing from Bronze manifest: {filename}"
            )

        if entry.get("size_bytes") != verified["size_bytes"]:
            raise ValueError(
                f"Source size mismatch in Bronze manifest: {filename}"
            )

        if (
            entry.get("sha256", "").lower()
            != verified["sha256"].lower()
        ):
            raise ValueError(
                f"Source SHA-256 mismatch in Bronze manifest: {filename}"
            )

    feature_definitions = load_feature_metadata(
        project_root
        / RAW_DATA_RELATIVE_PATH
        / FEATURE_METADATA_FILENAME
    )

    feature_names = [
        feature.name
        for feature in feature_definitions
    ]

    manifest_features = manifest.get("feature_schema")

    if not isinstance(manifest_features, list):
        raise TypeError(
            "Bronze manifest must contain a feature_schema list."
        )

    if len(manifest_features) != len(feature_definitions):
        raise ValueError(
            "Feature schema count does not match source metadata."
        )

    for definition, manifest_feature in zip(
        feature_definitions,
        manifest_features,
        strict=True,
    ):
        if manifest_feature.get("name") != definition.name:
            raise ValueError(
                "Feature schema name mismatch: "
                f"expected {definition.name}."
            )

        if (
            manifest_feature.get("source_feature_type")
            != definition.feature_type
        ):
            raise ValueError(
                f"Source feature type mismatch for {definition.name}."
            )

        if manifest_feature.get("parquet_type") != "string":
            raise ValueError(
                f"Bronze feature is not declared as a string: "
                f"{definition.name}."
            )

    file_entries = manifest.get("files")

    if not isinstance(file_entries, list):
        raise TypeError(
            "Bronze manifest must contain a files list."
        )

    file_entries_by_name = {}

    for entry in file_entries:
        if not isinstance(entry, dict):
            raise TypeError(
                "Every Bronze file entry must be a JSON object."
            )

        filename = entry.get("source_filename")

        if not isinstance(filename, str):
            raise TypeError(
                "A Bronze file entry has no valid source filename."
            )

        if filename in file_entries_by_name:
            raise ValueError(
                f"Duplicate Bronze file entry: {filename}"
            )

        file_entries_by_name[filename] = entry

    expected_source_files = set(DATA_FILENAMES)

    if set(file_entries_by_name) != expected_source_files:
        raise ValueError(
            "Bronze manifest does not contain exactly the four "
            "expected UNSW-NB15 data files."
        )

    expected_parquet_files = {
        f"{Path(filename).stem}.parquet"
        for filename in DATA_FILENAMES
    }

    actual_parquet_files = {
        path.name
        for path in output_directory.glob("*.parquet")
    }

    if actual_parquet_files != expected_parquet_files:
        raise ValueError(
            "Bronze directory contains an unexpected set of "
            "Parquet files."
        )

    results = []

    for filename in DATA_FILENAMES:
        print(
            f"Verifying every record in {filename}..."
        )

        file_manifest = file_entries_by_name[filename]

        # Pass the original ingestion chunk size separately.
        file_manifest = {
            **file_manifest,
            "ingestion_chunk_size_rows": chunk_size,
        }

        result = verify_bronze_file(
            project_root=project_root,
            output_directory=output_directory,
            filename=filename,
            file_manifest=file_manifest,
            feature_names=feature_names,
            compression=compression,
            batch_size=batch_size,
        )

        results.append(result)

        print(
            f"  Verified {result['records_verified']:,} records "
            f"in {result['row_groups']} row groups."
        )

    total_verified = sum(
        result["records_verified"]
        for result in results
    )

    manifest_total = manifest.get("total_records")

    if total_verified != manifest_total:
        raise ValueError(
            f"Total record mismatch: manifest says "
            f"{manifest_total:,}, verified {total_verified:,}."
        )

    return results


def main() -> None:
    """Run independent Bronze verification."""

    parser = argparse.ArgumentParser(
        description=(
            "Independently compare Bronze Parquet data "
            "against the original UNSW-NB15 CSV files."
        )
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=(
            "Number of rows to compare at a time. "
            f"Default: {DEFAULT_BATCH_SIZE}."
        ),
    )

    arguments = parser.parse_args()

    results = verify_bronze_dataset(
        batch_size=arguments.batch_size
    )

    total_verified = sum(
        result["records_verified"]
        for result in results
    )

    print()
    print("BRONZE VERIFICATION PASSED")
    print("=" * 60)
    print(f"Files verified:  {len(results)}")
    print(f"Records checked: {total_verified:,}")
    print("Feature values:  All 49 features compared.")
    print("Provenance:      All source filenames and record numbers checked.")
    print("Compression:     Verified.")
    print("Checksums:       Verified.")
    print("Schema:          Verified.")
    print("=" * 60)


if __name__ == "__main__":
    main()
