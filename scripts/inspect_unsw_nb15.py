
from collections import Counter
from pathlib import Path
import re

import pandas as pd


DATA_DIRECTORY = Path("data/raw/UNSW-NB15")

FEATURES_FILE = DATA_DIRECTORY / "NUSW-NB15_features.csv"

DATA_FILES = [
    "UNSW-NB15_1.csv",
    "UNSW-NB15_2.csv",
    "UNSW-NB15_3.csv",
    "UNSW-NB15_4.csv",
]

EXPECTED_TOTAL_ROWS = 2_540_044
CHUNK_SIZE = 250_000


def load_feature_names() -> list[str]:
    """Load the official feature names from the metadata file."""

    if not FEATURES_FILE.is_file():
        raise FileNotFoundError(
            f"Feature metadata is missing: {FEATURES_FILE}"
        )

    
    metadata = pd.read_csv(
    	FEATURES_FILE,
    	skipinitialspace=True,
    	encoding="cp1252",
    	engine="python",
    )


    metadata.columns = [
        str(column).strip()
        for column in metadata.columns
    ]

    name_column = next(
        (
            column
            for column in metadata.columns
            if column.casefold() == "name"
        ),
        None,
    )

    if name_column is None:
        raise ValueError(
            "Could not find the Name column in feature metadata. "
            f"Found columns: {metadata.columns.tolist()}"
        )

    raw_names = (
        metadata[name_column]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    # Remove accidental whitespace inside metadata names.
    # Example: "ct_src_ ltm" becomes "ct_src_ltm".
    feature_names = [
        re.sub(r"\s+", "", name)
        for name in raw_names
    ]

    if len(feature_names) != 49:
        raise ValueError(
            f"Expected 49 feature names, "
            f"but found {len(feature_names)}."
        )

    normalized_names = [
        name.casefold()
        for name in feature_names
    ]

    if len(set(normalized_names)) != 49:
        raise ValueError(
            "Duplicate feature names were found."
        )

    required_columns = {
        "label",
        "attack_cat",
        "stime",
        "ltime",
    }

    if not required_columns.issubset(
        set(normalized_names)
    ):
        raise ValueError(
            "Required columns are missing from metadata."
        )

    print("Successfully loaded 49 feature names.")
    print("\nFeature names:")

    for name in feature_names:
        print(f"  - {name}")

    return feature_names


def inspect_dataset(feature_names: list[str]) -> None:
    """Inspect all original CSV files without modifying them."""

    total_rows = 0

    combined_labels = Counter()
    combined_attack_categories = Counter()

    column_lookup = {
        name.casefold(): name
        for name in feature_names
    }

    label_column = column_lookup["label"]
    attack_category_column = column_lookup["attack_cat"]

    for filename in DATA_FILES:

        file_path = DATA_DIRECTORY / filename

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Required dataset file is missing: {file_path}"
            )

        print("\n" + "=" * 70)
        print(f"FILE: {filename}")
        print("=" * 70)

        # These CSV files contain no header row.
        # Use the metadata file to assign the correct column names.
        first_record = pd.read_csv(
            file_path,
            header=None,
            names=feature_names,
            nrows=1,
            low_memory=False,
        )

        if first_record.shape[1] != 49:
            raise ValueError(
                f"{filename} does not have 49 columns."
            )

        print(f"Number of columns: {first_record.shape[1]}")

        print("\nFirst record with correct column names:")
        print(first_record.to_string(index=False))

        file_rows = 0
        file_labels = Counter()
        file_attack_categories = Counter()

        # Process the complete file in chunks to limit RAM usage.
        for chunk in pd.read_csv(
            file_path,
            header=None,
            names=feature_names,
            chunksize=CHUNK_SIZE,
            low_memory=False,
        ):

            file_rows += len(chunk)

            labels = (
                chunk[label_column]
                .astype("string")
                .fillna("<MISSING>")
                .str.strip()
            )

            file_labels.update(
                labels.value_counts().to_dict()
            )

            categories = (
                chunk[attack_category_column]
                .astype("string")
                .fillna("<MISSING>")
                .str.strip()
            )

            file_attack_categories.update(
                categories.value_counts().to_dict()
            )

        total_rows += file_rows

        combined_labels.update(file_labels)
        combined_attack_categories.update(
            file_attack_categories
        )

        print(f"\nNumber of data rows: {file_rows:,}")

        print("\nBinary label distribution:")

        for label, count in sorted(file_labels.items()):
            print(f"  {label}: {count:,}")

        print("\nAttack category distribution:")

        for category, count in sorted(
            file_attack_categories.items()
        ):
            print(f"  {category}: {count:,}")

    print("\n" + "=" * 70)
    print("COMBINED DATASET SUMMARY")
    print("=" * 70)

    print(f"Total records: {total_rows:,}")
    print(f"Official reference: {EXPECTED_TOTAL_ROWS:,}")

    difference = total_rows - EXPECTED_TOTAL_ROWS

    print(f"Difference: {difference:+,}")

    if difference == 0:
        print("Record count matches the official reference.")
    else:
        print(
            "WARNING: Record count differs from the official "
            "reference. Investigate before proceeding."
        )

    print("\nCombined binary label distribution:")

    for label, count in sorted(combined_labels.items()):
        print(f"  {label}: {count:,}")

    print("\nCombined attack category distribution:")

    for category, count in sorted(
        combined_attack_categories.items()
    ):
        print(f"  {category}: {count:,}")

    print("\nInspection completed. Original files were not modified.")


def main() -> None:
    """Run the complete dataset inspection."""

    feature_names = load_feature_names()

    inspect_dataset(feature_names)


if __name__ == "__main__":
    main()
