from a1.data.profiling import (
    profile_dataset,
    write_profile_reports,
)
from a1.data.schema import (
    FEATURE_METADATA_FILENAME,
    RAW_DATA_RELATIVE_PATH,
    find_project_root,
    load_feature_metadata,
)


def main() -> None:
    """Run full-dataset UNSW-NB15 data-quality profiling."""

    project_root = find_project_root()

    data_directory = (
        project_root / RAW_DATA_RELATIVE_PATH
    )

    metadata_path = (
        data_directory / FEATURE_METADATA_FILENAME
    )

    feature_definitions = load_feature_metadata(
        metadata_path
    )

    print("=" * 70)
    print("UNSW-NB15 FULL-DATASET QUALITY PROFILING")
    print("=" * 70)

    print(f"Project root: {project_root}")
    print(f"Data directory: {data_directory}")
    print(f"Features: {len(feature_definitions)}")

    print("\nFeature types:")

    feature_type_counts = {}

    for feature in feature_definitions:
        feature_type_counts[feature.feature_type] = (
            feature_type_counts.get(feature.feature_type, 0) + 1
        )

    for feature_type, count in sorted(
        feature_type_counts.items()
    ):
        print(f"  {feature_type}: {count}")

    report = profile_dataset(
        data_directory=data_directory,
        feature_definitions=feature_definitions,
    )

    output_directory = (
        project_root / "reports" / "data_quality"
    )

    output_paths = write_profile_reports(
        report=report,
        output_directory=output_directory,
    )

    print("\n" + "=" * 70)
    print("DATASET SUMMARY")
    print("=" * 70)

    for file_result in report["files"]:
        print(
            f"{file_result['filename']}: "
            f"{file_result['records']:,} records"
        )

    print(
        f"\nTotal records: "
        f"{report['totals']['records']:,}"
    )

    print("\nFeatures with missing values:")

    features_with_missing_values = False

    for feature, count in report["missing_values"].items():

        if count > 0:
            features_with_missing_values = True

            fraction = report["missing_fractions"][feature]

            print(
                f"  {feature}: {count:,} "
                f"({fraction:.4%})"
            )

    if not features_with_missing_values:
        print("  None")

    print("\nNumeric validation findings:")

    numeric_findings_found = False

    for feature, stats in report["numeric_validation"].items():

        problems = []

        if stats["invalid_numeric_values"] > 0:
            problems.append(
                f"invalid numeric values: "
                f"{stats['invalid_numeric_values']:,}"
            )

        if stats["non_finite_values"] > 0:
            problems.append(
                f"non-finite values: "
                f"{stats['non_finite_values']:,}"
            )

        if stats["fractional_values"] > 0:
            problems.append(
                f"fractional values: "
                f"{stats['fractional_values']:,}"
            )

        if stats["negative_values"] > 0:
            problems.append(
                f"negative values: "
                f"{stats['negative_values']:,}"
            )

        if stats["binary_domain_violations"] > 0:
            problems.append(
                f"binary values outside 0/1: "
                f"{stats['binary_domain_violations']:,}"
            )

        if problems:
            numeric_findings_found = True

            print(
                f"  {feature}: "
                + "; ".join(problems)
            )

    if not numeric_findings_found:
        print("  No numeric anomalies detected.")

    print("\nTimestamp validation:")

    for feature, stats in (
        report["timestamp_validation"]["features"].items()
    ):
        print(f"  {feature}:")
        print(
            f"    Earliest UTC: {stats['earliest_utc']}"
        )
        print(
            f"    Latest UTC: {stats['latest_utc']}"
        )
        print(
            f"    Invalid numeric values: "
            f"{stats['invalid_numeric_values']:,}"
        )

    print(
        "  Rows where ltime precedes stime: "
        f"{report['timestamp_validation']['rows_where_ltime_precedes_stime']:,}"
    )

    print("\nLabel and attack-category distribution:")

    for row in report["label_attack_category_counts"]:

        category = row["attack_cat"]

        if category is None:
            category = "<MISSING>"

        print(
            f"  label={row['label']}, "
            f"attack_cat={category}: "
            f"{row['records']:,}"
        )

    print("\nReports created:")

    for report_name, report_path in output_paths.items():
        print(f"  {report_name}: {report_path}")

    print("\nProfiling completed.")
    print("Original CSV files were not modified.")


if __name__ == "__main__":
    main()