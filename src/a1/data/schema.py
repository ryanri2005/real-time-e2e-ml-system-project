import re
from dataclasses import dataclass
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

ALLOWED_FEATURE_TYPES = {
    "nominal",
    "integer",
    "float",
    "timestamp",
    "binary",
}


@dataclass(frozen=True)
class FeatureDefinition:
    """Metadata describing one UNSW-NB15 feature."""

    name: str
    feature_type: str
    description: str


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


def load_feature_metadata(
    metadata_path: Path,
) -> tuple[FeatureDefinition, ...]:
    """Load and validate feature names, types, and descriptions."""

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

    column_lookup = {
        str(column).strip().casefold(): column
        for column in metadata.columns
    }

    required_metadata_fields = {
        "name",
        "type",
    }

    missing_fields = (
        required_metadata_fields - set(column_lookup)
    )

    if missing_fields:
        raise ValueError(
            "Required metadata fields are missing: "
            f"{sorted(missing_fields)}"
        )

    name_column = column_lookup["name"]
    type_column = column_lookup["type"]
    description_column = column_lookup.get("description")

    feature_definitions = []

    for _, row in metadata.iterrows():

        raw_name = row[name_column]

        if pd.isna(raw_name):
            continue

        feature_name = re.sub(
            r"\s+",
            "",
            str(raw_name).strip(),
        ).casefold()

        if not feature_name:
            continue

        raw_type = row[type_column]

        if pd.isna(raw_type):
            raise ValueError(
                f"Missing feature type for {feature_name}."
            )

        feature_type = str(raw_type).strip().casefold()

        if feature_type not in ALLOWED_FEATURE_TYPES:
            raise ValueError(
                f"Unsupported feature type '{feature_type}' "
                f"for feature '{feature_name}'."
            )

        description = ""

        if description_column is not None:
            raw_description = row[description_column]

            if not pd.isna(raw_description):
                description = str(raw_description).strip()

        feature = FeatureDefinition(
            name=feature_name,
            feature_type=feature_type,
            description=description,
        )

        feature_definitions.append(feature)

    if len(feature_definitions) != EXPECTED_FEATURE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_FEATURE_COUNT} feature definitions, "
            f"but found {len(feature_definitions)}."
        )

    feature_names = [
        feature.name
        for feature in feature_definitions
    ]

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

    return tuple(feature_definitions)


def load_feature_names(
    metadata_path: Path,
) -> list[str]:
    """Load normalized feature names from the metadata file."""

    feature_definitions = load_feature_metadata(metadata_path)

    return [
        feature.name
        for feature in feature_definitions
    ]