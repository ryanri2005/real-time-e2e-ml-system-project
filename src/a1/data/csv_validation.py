import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MalformedRecordExample:
    """Details about one record with an unexpected field count."""

    record_number: int
    physical_line_number: int
    observed_field_count: int


@dataclass(frozen=True)
class CsvStructureReport:
    """Structural validation results for one CSV file."""

    path: Path
    expected_columns: int
    data_records: int
    blank_records: int
    valid_records: int
    malformed_records: int
    malformed_examples: tuple[MalformedRecordExample, ...]

    @property
    def is_valid(self) -> bool:
        """Check whether a nonempty file has valid record widths."""

        return (
            self.data_records > 0
            and self.malformed_records == 0
        )


def validate_csv_structure(
    file_path: Path,
    expected_columns: int,
    sample_limit: int = 5,
) -> CsvStructureReport:
    """Count CSV records and check their number of fields."""

    if not file_path.is_file():
        raise FileNotFoundError(
            f"CSV file not found: {file_path}"
        )

    if expected_columns <= 0:
        raise ValueError(
            "expected_columns must be greater than zero."
        )

    if sample_limit < 0:
        raise ValueError(
            "sample_limit cannot be negative."
        )

    data_records = 0
    blank_records = 0
    valid_records = 0
    malformed_records = 0

    malformed_examples = []

    with file_path.open(
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

                physical_line_number = reader.line_num

                if not row:
                    blank_records += 1
                    continue

                data_records += 1

                observed_field_count = len(row)

                if observed_field_count == expected_columns:
                    valid_records += 1
                    continue

                malformed_records += 1

                if len(malformed_examples) < sample_limit:
                    example = MalformedRecordExample(
                        record_number=data_records,
                        physical_line_number=physical_line_number,
                        observed_field_count=observed_field_count,
                    )

                    malformed_examples.append(example)

        except csv.Error as error:
            raise ValueError(
                f"CSV parsing failed for {file_path} "
                f"near physical line {reader.line_num}: {error}"
            ) from error

    return CsvStructureReport(
        path=file_path,
        expected_columns=expected_columns,
        data_records=data_records,
        blank_records=blank_records,
        valid_records=valid_records,
        malformed_records=malformed_records,
        malformed_examples=tuple(malformed_examples),
    )