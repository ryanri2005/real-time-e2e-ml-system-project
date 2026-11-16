
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

DATA_DIRECTORY = Path("data/raw/UNSW-NB15")
OUTPUT_DIRECTORY = Path("docs/datasets")

EXPECTED_FILES = [
    "UNSW-NB15_1.csv",
    "UNSW-NB15_2.csv",
    "UNSW-NB15_3.csv",
    "UNSW-NB15_4.csv",
    "NUSW-NB15_features.csv",
]


def calculate_sha256(file_path: Path) -> str:
    """Calculate the SHA-256 fingerprint of a file."""

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    manifest = {
        "dataset": "UNSW-NB15",
        "source": (
            "https://research.unsw.edu.au/projects/"
            "unsw-nb15-dataset"
        ),
        "generated_at_utc": datetime.now(
            UTC
        ).isoformat(),
        "files": [],
    }

    for filename in EXPECTED_FILES:
        file_path = DATA_DIRECTORY / filename

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Missing dataset file: {file_path}"
            )

        manifest["files"].append({
            "filename": filename,
            "size_bytes": file_path.stat().st_size,
            "sha256": calculate_sha256(file_path),
        })

    output_path = (
        OUTPUT_DIRECTORY / "unsw_nb15_manifest.json"
    )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=4)

    print(f"Manifest created: {output_path}")
    print(f"Files recorded: {len(manifest['files'])}")


if __name__ == "__main__":
    main()
