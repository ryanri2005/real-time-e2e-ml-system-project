
import csv
import hashlib
import json
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from a1.data.schema import DATA_FILENAMES


def _serialize_record(row: list[str]) -> bytes:
    """Serialize fields without delimiter ambiguity."""

    payload = bytearray()

    for value in row:
        encoded_value = value.encode("utf-8")

        payload.extend(
            len(encoded_value).to_bytes(8, byteorder="big")
        )

        payload.extend(encoded_value)

    return bytes(payload)


def _hash_record(payload: bytes) -> bytes:
    """Calculate a SHA-256 digest for a serialized record."""

    return hashlib.sha256(payload).digest()


def _create_database(
    connection: sqlite3.Connection,
    file_count: int,
) -> str:
    """Create the disk-backed duplicate index and SQL triggers."""

    file_count_columns = [
        f"file_{index}_count"
        for index in range(file_count)
    ]

    column_definitions = ", ".join(
        f"{column} INTEGER NOT NULL"
        for column in file_count_columns
    )

    connection.execute(
        f"""
        CREATE TABLE records (
            digest BLOB PRIMARY KEY,
            payload BLOB NOT NULL,
            occurrence_count INTEGER NOT NULL,
            first_file_index INTEGER NOT NULL,
            first_record_number INTEGER NOT NULL,
            {column_definitions},
            last_file_index INTEGER NOT NULL,
            last_record_number INTEGER NOT NULL
        ) WITHOUT ROWID
        """
    )

    connection.execute(
        """
        CREATE TABLE duplicate_occurrences (
            digest BLOB NOT NULL,
            file_index INTEGER NOT NULL,
            record_number INTEGER NOT NULL,
            PRIMARY KEY (
                digest,
                file_index,
                record_number
            )
        ) WITHOUT ROWID
        """
    )

    connection.execute(
        """
        CREATE TRIGGER prevent_sha256_collision
        BEFORE UPDATE OF payload ON records
        WHEN OLD.payload != NEW.payload
        BEGIN
            SELECT RAISE(
                ABORT,
                'SHA-256 collision: different records share a digest'
            );
        END
        """
    )

    connection.execute(
        """
        CREATE TRIGGER capture_duplicate_occurrences
        AFTER UPDATE OF occurrence_count ON records
        WHEN NEW.occurrence_count >= 2
        BEGIN

            INSERT OR IGNORE INTO duplicate_occurrences (
                digest,
                file_index,
                record_number
            )
            SELECT
                NEW.digest,
                OLD.first_file_index,
                OLD.first_record_number
            WHERE OLD.occurrence_count = 1;

            INSERT OR IGNORE INTO duplicate_occurrences (
                digest,
                file_index,
                record_number
            )
            VALUES (
                NEW.digest,
                NEW.last_file_index,
                NEW.last_record_number
            );

        END
        """
    )

    connection.commit()

    columns = [
        "digest",
        "payload",
        "occurrence_count",
        "first_file_index",
        "first_record_number",
        *file_count_columns,
        "last_file_index",
        "last_record_number",
    ]

    update_statements = [
        "payload = excluded.payload",
        "occurrence_count = records.occurrence_count + 1",
    ]

    for column in file_count_columns:

        update_statements.append(
            f"{column} = records.{column} + excluded.{column}"
        )

    update_statements.extend([
        "last_file_index = excluded.last_file_index",
        "last_record_number = excluded.last_record_number",
    ])

    placeholders = ", ".join(
        "?"
        for _ in columns
    )

    column_names = ", ".join(columns)

    update_sql = ",\n".join(update_statements)

    return f"""
        INSERT INTO records ({column_names})
        VALUES ({placeholders})
        ON CONFLICT(digest) DO UPDATE SET
            {update_sql}
    """


def _flush_batch(
    connection: sqlite3.Connection,
    insert_sql: str,
    batch: list[tuple[Any, ...]],
) -> None:
    """Insert a batch of records and detect possible hash collisions."""

    if not batch:
        return

    try:

        connection.executemany(
            insert_sql,
            batch,
        )

        connection.commit()

    except sqlite3.IntegrityError as error:

        connection.rollback()

        if "SHA-256 collision" in str(error):

            raise RuntimeError(
                "A SHA-256 collision was detected. "
                "Different records produced the same digest."
            ) from error

        raise

    batch.clear()


def _get_summary(
    connection: sqlite3.Connection,
    file_count: int,
) -> dict[str, int]:
    """Calculate overall and within/across-file duplicate statistics."""

    file_count_columns = [
        f"file_{index}_count"
        for index in range(file_count)
    ]

    within_file_condition = " OR ".join(
        f"{column} > 1"
        for column in file_count_columns
    )

    file_presence_expression = " + ".join(
        f"CASE WHEN {column} > 0 THEN 1 ELSE 0 END"
        for column in file_count_columns
    )

    same_file_extra_expression = " + ".join(
        (
            f"CASE WHEN {column} > 1 "
            f"THEN {column} - 1 ELSE 0 END"
        )
        for column in file_count_columns
    )

    query = f"""
        SELECT
            COUNT(*),

            COALESCE(
                SUM(occurrence_count),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN occurrence_count > 1 THEN 1
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN occurrence_count > 1
                        THEN occurrence_count
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN occurrence_count > 1
                        THEN occurrence_count - 1
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN occurrence_count > 1
                        AND ({within_file_condition})
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN occurrence_count > 1
                        AND ({file_presence_expression}) >= 2
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ),

            COALESCE(
                SUM(
                    CASE
                        WHEN occurrence_count > 1
                        THEN ({same_file_extra_expression})
                        ELSE 0
                    END
                ),
                0
            )

        FROM records
    """

    result = connection.execute(query).fetchone()

    names = (
        "unique_records",
        "records_accounted_for",
        "duplicate_groups",
        "records_in_duplicate_groups",
        "duplicate_excess_records",
        "same_file_duplicate_groups",
        "cross_file_duplicate_groups",
        "same_file_extra_occurrences",
    )

    return {
        name: int(value)
        for name, value in zip(names, result)
    }


def _write_duplicate_group_report(
    connection: sqlite3.Connection,
    output_path: Path,
    filenames: tuple[str, ...],
) -> int:
    """Write one row for every exact duplicate group."""

    file_count_columns = [
        f"file_{index}_count"
        for index in range(len(filenames))
    ]

    selected_columns = ", ".join(file_count_columns)

    query = f"""
        SELECT
            digest,
            occurrence_count,
            first_file_index,
            first_record_number,
            {selected_columns}
        FROM records
        WHERE occurrence_count > 1
        ORDER BY occurrence_count DESC, digest
    """

    headers = [
        "sha256",
        "occurrences",
        "extra_occurrences",
        "number_of_files",
        "first_file",
        "first_record_number",
        *[
            f"records_in_{filename}"
            for filename in filenames
        ],
    ]

    group_count = 0

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.writer(file)

        writer.writerow(headers)

        cursor = connection.execute(query)

        while True:

            rows = cursor.fetchmany(1000)

            if not rows:
                break

            for row in rows:

                (
                    digest,
                    occurrences,
                    first_file_index,
                    first_record_number,
                    *file_counts,
                ) = row

                number_of_files = sum(
                    count > 0
                    for count in file_counts
                )

                writer.writerow([
                    bytes(digest).hex(),
                    occurrences,
                    occurrences - 1,
                    number_of_files,
                    filenames[first_file_index],
                    first_record_number,
                    *file_counts,
                ])

                group_count += 1

    return group_count


def _write_duplicate_occurrence_report(
    connection: sqlite3.Connection,
    output_path: Path,
    filenames: tuple[str, ...],
) -> int:
    """Write every source location belonging to a duplicate group."""

    query = """
        SELECT
            locations.digest,
            locations.file_index,
            locations.record_number,
            records.occurrence_count

        FROM duplicate_occurrences AS locations

        INNER JOIN records
            ON locations.digest = records.digest

        ORDER BY
            locations.digest,
            locations.file_index,
            locations.record_number
    """

    occurrence_count = 0

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "sha256",
            "filename",
            "record_number",
            "group_occurrences",
        ])

        cursor = connection.execute(query)

        while True:

            rows = cursor.fetchmany(1000)

            if not rows:
                break

            for digest, file_index, record_number, group_count in rows:

                writer.writerow([
                    bytes(digest).hex(),
                    filenames[file_index],
                    record_number,
                    group_count,
                ])

                occurrence_count += 1

    return occurrence_count


def analyze_duplicates(
    data_directory: Path,
    output_directory: Path,
    expected_columns: int,
    data_filenames: tuple[str, ...] = DATA_FILENAMES,
    batch_size: int = 10_000,
) -> dict[str, Any]:
    """Detect exact duplicate records using a temporary SQLite index."""

    if expected_columns <= 0:
        raise ValueError(
            "expected_columns must be greater than zero."
        )

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than zero."
        )

    if not data_filenames:
        raise ValueError(
            "At least one CSV filename is required."
        )

    if len(set(data_filenames)) != len(data_filenames):
        raise ValueError(
            "Duplicate filenames were provided."
        )

    for filename in data_filenames:

        file_path = data_directory / filename

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Dataset file not found: {file_path}"
            )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_path = (
        output_directory / "unsw_nb15_duplicate_summary.json"
    )

    groups_path = (
        output_directory / "unsw_nb15_duplicate_groups.csv"
    )

    occurrences_path = (
        output_directory / "unsw_nb15_duplicate_occurrences.csv"
    )

    file_results = []
    total_records = 0

    with tempfile.TemporaryDirectory(
        prefix="a1_unsw_nb15_duplicates_"
    ) as temporary_directory:

        database_path = (
            Path(temporary_directory) / "duplicate_index.sqlite3"
        )

        connection = sqlite3.connect(database_path)

        try:

            # This database is temporary and rebuildable.
            # These settings prioritize speed over crash recovery.
            connection.execute("PRAGMA journal_mode = OFF")
            connection.execute("PRAGMA synchronous = OFF")
            connection.execute("PRAGMA temp_store = FILE")
            connection.execute("PRAGMA cache_size = -65536")

            insert_sql = _create_database(
                connection,
                len(data_filenames),
            )

            for file_index, filename in enumerate(data_filenames):

                file_path = data_directory / filename

                file_records = 0
                batch = []

                file_counts = [
                    0
                    for _ in data_filenames
                ]

                file_counts[file_index] = 1

                print(f"\nScanning: {filename}")

                try:

                    with file_path.open(
                        "r",
                        encoding="utf-8-sig",
                        newline="",
                    ) as file:

                        reader = csv.reader(
                            file,
                            strict=True,
                        )

                        for record_number, row in enumerate(
                            reader,
                            start=1,
                        ):

                            if len(row) != expected_columns:

                                raise ValueError(
                                    f"Unexpected field count in "
                                    f"{filename}, record {record_number}: "
                                    f"expected {expected_columns}, "
                                    f"found {len(row)}."
                                )

                            payload = _serialize_record(row)

                            digest = _hash_record(payload)

                            if len(digest) != 32:

                                raise ValueError(
                                    "The duplicate hash function "
                                    "must produce a 32-byte SHA-256 digest."
                                )

                            batch.append((
                                digest,
                                payload,
                                1,
                                file_index,
                                record_number,
                                *file_counts,
                                file_index,
                                record_number,
                            ))

                            file_records += 1

                            if len(batch) >= batch_size:

                                _flush_batch(
                                    connection,
                                    insert_sql,
                                    batch,
                                )

                except csv.Error as error:

                    raise ValueError(
                        f"CSV parsing failed for {filename} "
                        f"near physical line {reader.line_num}: {error}"
                    ) from error

                _flush_batch(
                    connection,
                    insert_sql,
                    batch,
                )

                total_records += file_records

                file_results.append({
                    "filename": filename,
                    "records": file_records,
                    "size_bytes": file_path.stat().st_size,
                })

                print(
                    f"Records scanned: {file_records:,}"
                )

            summary = _get_summary(
                connection,
                len(data_filenames),
            )

            if summary["records_accounted_for"] != total_records:

                raise RuntimeError(
                    "Duplicate-index record accounting failed: "
                    f"scanned {total_records:,}, "
                    f"indexed {summary['records_accounted_for']:,}."
                )

            group_count = _write_duplicate_group_report(
                connection,
                groups_path,
                data_filenames,
            )

            occurrence_count = _write_duplicate_occurrence_report(
                connection,
                occurrences_path,
                data_filenames,
            )

            if group_count != summary["duplicate_groups"]:

                raise RuntimeError(
                    "Duplicate-group report count does not match "
                    "the database summary."
                )

            if occurrence_count != (
                summary["records_in_duplicate_groups"]
            ):

                raise RuntimeError(
                    "Duplicate-occurrence report count does not match "
                    "the database summary."
                )

            report = {
                "dataset": "UNSW-NB15",
                "generated_at_utc": datetime.now(
                    UTC
                ).isoformat(),
                "method": {
                    "algorithm": "SHA-256",
                    "record_definition": (
                        "Two records are duplicates when all parsed "
                        "CSV field values are identical."
                    ),
                    "serialization": (
                        "Each UTF-8 field is encoded with its byte "
                        "length before its contents. This prevents "
                        "delimiter ambiguity."
                    ),
                    "normalization": (
                        "No trimming, case conversion, missing-value "
                        "replacement, or other field normalization "
                        "is performed."
                    ),
                    "csv_formatting": (
                        "CSV quoting and line-ending differences do not "
                        "create different records when parsed field "
                        "values are identical."
                    ),
                    "collision_protection": (
                        "The complete serialized record is compared "
                        "whenever an existing digest is encountered."
                    ),
                    "record_numbers": (
                        "Source locations use one-based logical CSV "
                        "record numbers."
                    ),
                    "raw_data_handling": (
                        "Original CSV files are read only and are never "
                        "modified."
                    ),
                },
                "expected_columns": expected_columns,
                "total_records": total_records,
                "unique_records": summary["unique_records"],
                "duplicate_groups": summary["duplicate_groups"],
                "records_in_duplicate_groups": (
                    summary["records_in_duplicate_groups"]
                ),
                "duplicate_excess_records": (
                    summary["duplicate_excess_records"]
                ),
                "same_file_duplicate_groups": (
                    summary["same_file_duplicate_groups"]
                ),
                "cross_file_duplicate_groups": (
                    summary["cross_file_duplicate_groups"]
                ),
                "same_file_extra_occurrences": (
                    summary["same_file_extra_occurrences"]
                ),
                "duplicate_occurrence_locations": occurrence_count,
                "files": file_results,
                "output_files": {
                    "summary": summary_path.name,
                    "groups": groups_path.name,
                    "occurrences": occurrences_path.name,
                },
            }

            if (
                summary["unique_records"]
                + summary["duplicate_excess_records"]
                != total_records
            ):

                raise RuntimeError(
                    "Unique and duplicate record counts "
                    "do not reconcile with the total."
                )

            with summary_path.open(
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    report,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            return report

        finally:

            connection.close()
