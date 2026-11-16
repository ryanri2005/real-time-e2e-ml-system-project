import re
from pathlib import Path

import pandas as pd

RAW_DATA_RELATIVE_PATH = Path("data/raw/UNSW-NB15")

FEATURE_METADATA_FILENAME = "NUSW-NB15_features.csv"

DATA_FILENAMES = (
    "UNSW-NB15_1.csv",
    "UNSW-NB15_2.csv",
    "UNSW-NB15_3.csv",
    "UNSW-NB15_4.csv",
)

EXPECTED_FEATURE_COUNT = 49

REQUIRED_COLUMNS = {
    "label",
    "attack_cat",
    "stime",
    "ltime",
}


def find_project_root(
    start_path: Path | None = None,
) -> Path:
    """Find the project root using pyproject.toml."""

    if start_path is None:
        start_path = Path.cwd()

    starting_directory = start_path.resolve()

    for directory in (
        starting_directory,
        *starting_directory.parents,
    ):
        project_file = directory / "pyproject.toml"

        if project_file.is_file():
            return directory

    raise FileNotFoundError(
        "Could not locate the project root. "
        "Expected to find pyproject.toml."
    )


def load_feature_names(
    metadata_path: Path,
) -> list[str]:
    """Load and validate the official UNSW-NB15 feature names."""

    if not metadata_path.is_file():
        raise FileNotFoundError(
            f"Feature metadata file not found: {metadata_path}"
        )

    metadata = pd.read_csv(
        metadata_path,
        skipinitialspace=True,
        encoding="cp1252",
        engine="python",
    )

    metadata.columns = [
        str(column).strip()
        for column in metadata.columns
    ]

    name_column = None

    for column in metadata.columns:
        if column.casefold() == "name":
            name_column = column
            break

    if name_column is None:
        raise ValueError(
            "Could not find the Name column "
            "in the feature metadata."
        )

    raw_names = (
        metadata[name_column]
        .dropna()
        .astype(str)
        .tolist()
    )

    feature_names = []

    for raw_name in raw_names:
        cleaned_name = re.sub(
            r"\s+",
            "",
            raw_name.strip(),
        )

        if cleaned_name:
            feature_names.append(cleaned_name.casefold())

    if len(feature_names) != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_FEATURE_COUNT} feature names, "
            f"but found {len(feature_names)}."
        )

    if len(set(feature_names)) != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            "Duplicate feature names were found "
            "after normalization."
        )

    missing_columns = REQUIRED_COLUMNS - set(feature_names)

    if missing_columns:
        raise ValueError(
            "Required columns are missing: "
            f"{sorted(missing_columns)}"
        )

    return feature_names