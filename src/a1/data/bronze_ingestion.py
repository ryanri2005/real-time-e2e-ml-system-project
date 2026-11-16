
import csv
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from a1.data.schema import (
    DATA_FILENAMES,
    FEATURE_METADATA_FILENAME,
    RAW_DATA_RELATIVE_PATH,
    find_project_root,
    load_feature_metadata,
)

SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "docs/datasets/unsw_nb15_manifest.json"
)

BRONZE_OUTPUT_RELATIVE_PATH = Path(
    "data/processed/bronze"
)

DEFAULT_CHUNK_SIZE = 25_000

SOURCE_COLUMNS = (
    "_source_file",
    "_source_record_number",
)


@dataclass(frozen=True)
class BronzeFileResult:
    """Results for one source CSV converted to Parquet."""

    source_filename: str
    parquet_filename: str
    record_count: int
    output_size_bytes: int
    row_group_count: int
    source_sha256: str
    output_sha256: str


@dataclass(frozen=True)
class BronzeIngestionResult:
    """Combined results of a complete Bronze ingestion run."""

    output_directory: Path
    total_records: int
    files: tuple[BronzeFileResult, ...]
    manifest_path: Path


def calculate_sha256(
    file_path: Path,
    read_size: int = 1024 * 1024,
) -> str:
    """Calculate a file's SHA-256 fingerprint."""

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(read_size),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def verify_source_manifest(
    project_root: Path,
) -> dict[str, dict]:
    """Verify every original dataset file against its manifest."""

    manifest_path = (
        project_root / SOURCE_MANIFEST_RELATIVE_PATH
    )

    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Source manifest not found: {manifest_path}"
        )

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        manifest = json.load(file)

    if not isinstance(manifest, dict):
        raise TypeError(
            "Source manifest must contain a JSON object."
        )

    if manifest.get("dataset") != "UNSW-NB15":
        raise ValueError(
            "Source manifest does not describe UNSW-NB15."
        )

    entries = manifest.get("files")

    if not isinstance(entries, list):
        raise TypeError(
            "Source manifest must contain a files list."
        )

    entries_by_name = {}

    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError(
                "Every source manifest entry must be a JSON object."
            )

        filename = entry.get("filename")

        if not isinstance(filename, str):
            raise TypeError(
                "A source manifest entry has no valid filename."
            )

        if filename in entries_by_name:
            raise ValueError(
                f"Duplicate manifest entry: {filename}"
            )

        entries_by_name[filename] = entry

    expected_filenames = (
        *DATA_FILENAMES,
        FEATURE_METADATA_FILENAME,
    )

    missing_entries = (
        set(expected_filenames) - set(entries_by_name)
    )

    if missing_entries:
        raise ValueError(
            "Source manifest is missing entries: "
            f"{sorted(missing_entries)}"
        )

    data_directory = (
        project_root / RAW_DATA_RELATIVE_PATH
    )

    verified_entries = {}

    for filename in expected_filenames:
        file_path = data_directory / filename

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Source file not found: {file_path}"
            )

        entry = entries_by_name[filename]

        expected_size = entry.get("size_bytes")
        expected_hash = entry.get("sha256")

        if (
            isinstance(expected_size, bool)
            or not isinstance(expected_size, int)
        ):
            raise TypeError(
                f"Invalid size type in source manifest: {filename}"
            )

        if not isinstance(expected_hash, str):
            raise TypeError(
                f"Invalid SHA-256 type in source manifest: {filename}"
            )

        if (
            len(expected_hash) != 64
            or any(
                character not in "0123456789abcdefABCDEF"
                for character in expected_hash
            )
        ):
            raise ValueError(
                f"Invalid SHA-256 value in source manifest: {filename}"
            )

        actual_size = file_path.stat().st_size

        if actual_size != expected_size:
            raise ValueError(
                f"File size mismatch for {filename}: "
                f"expected {expected_size}, "
                f"found {actual_size}."
            )

        actual_hash = calculate_sha256(file_path)

        if actual_hash.lower() != expected_hash.lower():
            raise ValueError(
                f"SHA-256 mismatch for {filename}. "
                "The source file may have changed."
            )

        verified_entries[filename] = {
            "size_bytes": actual_size,
            "sha256": actual_hash,
        }

    return verified_entries


def _write_csv_to_parquet(
    input_path: Path,
    output_path: Path,
    feature_names: list[str],
    chunk_size: int,
    compression: str,
) -> BronzeFileResult:
    """Stream one headerless CSV into a Parquet file."""

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if not feature_names:
        raise ValueError(
            "feature_names cannot be empty."
        )

    reserved_names = set(SOURCE_COLUMNS)
    collisions = reserved_names.intersection(feature_names)

    if collisions:
        raise ValueError(
            "Feature names conflict with provenance columns: "
            f"{sorted(collisions)}"
        )

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Input CSV not found: {input_path}"
        )

    arrow_schema = pa.schema(
        [
            *[
                pa.field(
                    name,
                    pa.string(),
                    nullable=False,
                )
                for name in feature_names
            ],
            pa.field(
                "_source_file",
                pa.string(),
                nullable=False,
            ),
            pa.field(
                "_source_record_number",
                pa.int64(),
                nullable=False,
            ),
        ]
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        output_path.name + ".tmp"
    )

    if temporary_path.exists():
        raise FileExistsError(
            f"Temporary output already exists: {temporary_path}"
        )

    column_buffers = {
        name: []
        for name in feature_names
    }

    source_file_buffer = []
    record_number_buffer = []

    record_count = 0

    def flush_chunk(
        writer: pq.ParquetWriter,
    ) -> None:
        """Write one buffered chunk as a Parquet row group."""

        if not record_number_buffer:
            return

        arrays = {
            name: pa.array(
                column_buffers[name],
                type=pa.string(),
            )
            for name in feature_names
        }

        arrays["_source_file"] = pa.array(
            source_file_buffer,
            type=pa.string(),
        )

        arrays["_source_record_number"] = pa.array(
            record_number_buffer,
            type=pa.int64(),
        )

        table = pa.Table.from_pydict(
            arrays,
            schema=arrow_schema,
        )

        writer.write_table(
            table,
            row_group_size=len(record_number_buffer),
        )

        for values in column_buffers.values():
            values.clear()

        source_file_buffer.clear()
        record_number_buffer.clear()

    try:
        with pq.ParquetWriter(
            temporary_path,
            arrow_schema,
            compression=compression,
            use_dictionary=True,
            write_statistics=True,
        ) as writer:

            with input_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as file:

                reader = csv.reader(
                    file,
                    strict=True,
                )

                try:
                    for row in reader:
                        physical_line = reader.line_num

                        if not row:
                            raise ValueError(
                                f"Blank CSV record in {input_path.name} "
                                f"near physical line {physical_line}."
                            )

                        if len(row) != len(feature_names):
                            raise ValueError(
                                f"Incorrect field count in "
                                f"{input_path.name}, "
                                f"record {record_count + 1}: "
                                f"expected {len(feature_names)}, "
                                f"found {len(row)}."
                            )

                        record_count += 1

                        for index, value in enumerate(row):
                            column_buffers[
                                feature_names[index]
                            ].append(value)

                        source_file_buffer.append(
                            input_path.name
                        )

                        record_number_buffer.append(
                            record_count
                        )

                        if len(record_number_buffer) >= chunk_size:
                            flush_chunk(writer)

                except csv.Error as error:
                    raise ValueError(
                        f"CSV parsing failed in {input_path.name} "
                        f"near physical line {reader.line_num}: {error}"
                    ) from error

            flush_chunk(writer)

            if record_count == 0:
                raise ValueError(
                    f"Source CSV contains no records: {input_path}"
                )

        os.replace(
            temporary_path,
            output_path,
        )

    finally:
        temporary_path.unlink(missing_ok=True)

    parquet_file = pq.ParquetFile(output_path)

    return BronzeFileResult(
        source_filename=input_path.name,
        parquet_filename=output_path.name,
        record_count=record_count,
        output_size_bytes=output_path.stat().st_size,
        row_group_count=parquet_file.metadata.num_row_groups,
        source_sha256=calculate_sha256(input_path),
        output_sha256=calculate_sha256(output_path),
    )


def ingest_unsw_nb15_bronze(
    project_root: Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    compression: str = "zstd",
) -> BronzeIngestionResult:
    """Build the complete raw-preserving UNSW-NB15 Bronze dataset."""

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if project_root is None:
        project_root = find_project_root()

    project_root = project_root.resolve()

    output_directory = (
        project_root / BRONZE_OUTPUT_RELATIVE_PATH
    )

    if output_directory.exists():
        raise FileExistsError(
            "Bronze output already exists. "
            f"Refusing to overwrite: {output_directory}"
        )

    verified_sources = verify_source_manifest(
        project_root
    )

    data_directory = (
        project_root / RAW_DATA_RELATIVE_PATH
    )

    metadata_path = (
        data_directory / FEATURE_METADATA_FILENAME
    )

    feature_definitions = load_feature_metadata(
        metadata_path
    )

    feature_names = [
        feature.name
        for feature in feature_definitions
    ]

    output_parent = output_directory.parent

    output_parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    staging_directory = Path(
        tempfile.mkdtemp(
            prefix=".bronze-staging-",
            dir=output_parent,
        )
    )

    file_results = []

    try:
        for filename in DATA_FILENAMES:
            input_path = data_directory / filename

            output_path = (
                staging_directory
                / f"{Path(filename).stem}.parquet"
            )

            result = _write_csv_to_parquet(
                input_path=input_path,
                output_path=output_path,
                feature_names=feature_names,
                chunk_size=chunk_size,
                compression=compression,
            )

            expected_source_hash = (
                verified_sources[filename]["sha256"]
            )

            if result.source_sha256 != expected_source_hash:
                raise ValueError(
                    f"Source file changed during ingestion: {filename}"
                )

            file_results.append(result)

        total_records = sum(
            result.record_count
            for result in file_results
        )

        source_file_records = []

        expected_source_filenames = (
            *DATA_FILENAMES,
            FEATURE_METADATA_FILENAME,
        )

        for filename in expected_source_filenames:
            source_file_records.append({
                "filename": filename,
                **verified_sources[filename],
            })

        manifest = {
            "dataset": "UNSW-NB15",
            "layer": "bronze",
            "generated_at_utc": datetime.now(
                UTC
            ).isoformat(),
            "chunk_size_rows": chunk_size,
            "compression": compression,
            "source_manifest": str(
                SOURCE_MANIFEST_RELATIVE_PATH
            ),
            "source_files": source_file_records,
            "feature_schema": [
                {
                    "name": feature.name,
                    "source_feature_type": feature.feature_type,
                    "parquet_type": "string",
                    "description": feature.description,
                }
                for feature in feature_definitions
            ],
            "provenance_schema": [
                {
                    "name": "_source_file",
                    "type": "string",
                },
                {
                    "name": "_source_record_number",
                    "type": "int64",
                },
            ],
            "total_records": total_records,
            "files": [
                asdict(result)
                for result in file_results
            ],
        }

        source_manifest_path = (
            project_root / SOURCE_MANIFEST_RELATIVE_PATH
        )

        with source_manifest_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            source_manifest_data = json.load(file)

        manifest["source_manifest_generated_at_utc"] = (
            source_manifest_data.get("generated_at_utc")
        )

        manifest_path = (
            staging_directory / "ingestion_manifest.json"
        )

        with manifest_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:

            json.dump(
                manifest,
                file,
                indent=2,
                ensure_ascii=False,
            )

            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        staging_directory.rename(
            output_directory
        )

    except Exception:
        shutil.rmtree(
            staging_directory,
            ignore_errors=True,
        )
        raise

    published_manifest = (
        output_directory / "ingestion_manifest.json"
    )

    return BronzeIngestionResult(
        output_directory=output_directory,
        total_records=total_records,
        files=tuple(file_results),
        manifest_path=published_manifest,
    )
