from a1.data.csv_validation import (
    validate_csv_structure,
)
from a1.data.schema import (
    DATA_FILENAMES,
    FEATURE_METADATA_FILENAME,
    RAW_DATA_RELATIVE_PATH,
    find_project_root,
    load_feature_names,
)


def main() -> None:
    """Validate the structure of all UNSW-NB15 CSV files."""

    project_root = find_project_root()

    data_directory = (
        project_root / RAW_DATA_RELATIVE_PATH
    )

    metadata_path = (
        data_directory / FEATURE_METADATA_FILENAME
    )

    feature_names = load_feature_names(metadata_path)

    expected_columns = len(feature_names)

    print("=" * 70)
    print("UNSW-NB15 CSV STRUCTURAL VALIDATION")
    print("=" * 70)

    print(f"Project root: {project_root}")
    print(f"Data directory: {data_directory}")
    print(f"Expected columns: {expected_columns}")

    print("\nNormalized feature names:")

    for feature_name in feature_names:
        print(f"  {feature_name}")

    total_records = 0
    total_blank_records = 0
    total_valid_records = 0
    total_malformed_records = 0

    all_files_valid = True

    for filename in DATA_FILENAMES:

        file_path = data_directory / filename

        print("\n" + "=" * 70)
        print(f"FILE: {filename}")
        print("=" * 70)

        report = validate_csv_structure(
            file_path=file_path,
            expected_columns=expected_columns,
        )

        total_records += report.data_records
        total_blank_records += report.blank_records
        total_valid_records += report.valid_records
        total_malformed_records += report.malformed_records

        print(f"Data records: {report.data_records:,}")
        print(f"Blank records: {report.blank_records:,}")
        print(f"Valid records: {report.valid_records:,}")
        print(f"Malformed records: {report.malformed_records:,}")

        if report.is_valid:
            print("Structural result: PASSED")
        else:
            all_files_valid = False

            print("Structural result: FAILED")

            print("\nMalformed record examples:")

            for example in report.malformed_examples:
                print(
                    f"  Record {example.record_number:,}: "
                    f"physical line {example.physical_line_number:,}, "
                    f"found {example.observed_field_count} fields"
                )

    print("\n" + "=" * 70)
    print("COMBINED VALIDATION SUMMARY")
    print("=" * 70)

    print(f"Total data records: {total_records:,}")
    print(f"Total blank records: {total_blank_records:,}")
    print(f"Total valid records: {total_valid_records:,}")
    print(f"Total malformed records: {total_malformed_records:,}")

    if all_files_valid:
        print("\nALL FOUR CSV FILES PASSED STRUCTURAL VALIDATION.")
    else:
        print("\nSTRUCTURAL VALIDATION FAILED.")

        raise SystemExit(1)


if __name__ == "__main__":
    main()