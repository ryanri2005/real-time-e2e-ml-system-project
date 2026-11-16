from a1.data.duplicate_analysis import (
    analyze_duplicates,
)
from a1.data.schema import (
    FEATURE_METADATA_FILENAME,
    RAW_DATA_RELATIVE_PATH,
    find_project_root,
    load_feature_names,
)


def main() -> None:
    """Run full-dataset UNSW-NB15 exact duplicate analysis."""

    project_root = find_project_root()

    data_directory = (
        project_root / RAW_DATA_RELATIVE_PATH
    )

    metadata_path = (
        data_directory / FEATURE_METADATA_FILENAME
    )

    feature_names = load_feature_names(metadata_path)

    output_directory = (
        project_root / "reports" / "data_quality"
    )

    print("=" * 70)
    print("UNSW-NB15 FULL-DATASET DUPLICATE ANALYSIS")
    print("=" * 70)

    print(f"Project root: {project_root}")
    print(f"Data directory: {data_directory}")
    print(f"Expected fields per record: {len(feature_names)}")

    report = analyze_duplicates(
        data_directory=data_directory,
        output_directory=output_directory,
        expected_columns=len(feature_names),
    )

    print("\n" + "=" * 70)
    print("DUPLICATE ANALYSIS SUMMARY")
    print("=" * 70)

    print(
        f"Total records: "
        f"{report['total_records']:,}"
    )

    print(
        f"Unique records: "
        f"{report['unique_records']:,}"
    )

    print(
        f"Duplicate groups: "
        f"{report['duplicate_groups']:,}"
    )

    print(
        f"Records in duplicate groups: "
        f"{report['records_in_duplicate_groups']:,}"
    )

    print(
        f"Duplicate excess records: "
        f"{report['duplicate_excess_records']:,}"
    )

    print(
        f"Within-file duplicate groups: "
        f"{report['same_file_duplicate_groups']:,}"
    )

    print(
        f"Cross-file duplicate groups: "
        f"{report['cross_file_duplicate_groups']:,}"
    )

    print(
        f"Extra occurrences within individual files: "
        f"{report['same_file_extra_occurrences']:,}"
    )

    print(
        f"Duplicate source locations recorded: "
        f"{report['duplicate_occurrence_locations']:,}"
    )

    print("\nReports created:")

    for report_name, filename in report["output_files"].items():

        print(
            f"  {report_name}: "
            f"{output_directory / filename}"
        )

    print("\nDuplicate analysis completed.")
    print("Original CSV files were not modified.")
    print("Temporary SQLite index was removed.")


if __name__ == "__main__":
    main()