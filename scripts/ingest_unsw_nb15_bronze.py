import argparse

from a1.data.bronze_ingestion import (
    DEFAULT_CHUNK_SIZE,
    ingest_unsw_nb15_bronze,
)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line options for Bronze ingestion."""

    parser = argparse.ArgumentParser(
        description=(
            "Convert the original UNSW-NB15 CSV files "
            "into raw-preserving Bronze Parquet files."
        )
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=(
            "Number of CSV records to process per chunk. "
            f"Default: {DEFAULT_CHUNK_SIZE}."
        ),
    )

    parser.add_argument(
        "--compression",
        choices=(
            "zstd",
            "snappy",
            "gzip",
            "brotli",
            "lz4",
        ),
        default="zstd",
        help="Parquet compression codec. Default: zstd.",
    )

    return parser.parse_args()


def main() -> None:
    """Run Bronze ingestion and print a summary."""

    arguments = parse_arguments()

    result = ingest_unsw_nb15_bronze(
        chunk_size=arguments.chunk_size,
        compression=arguments.compression,
    )

    print()
    print("BRONZE INGESTION COMPLETED")
    print("=" * 60)
    print(f"Output directory: {result.output_directory}")
    print(f"Total records:    {result.total_records:,}")
    print(f"Files converted:  {len(result.files)}")
    print()

    for file_result in result.files:
        size_mib = (
            file_result.output_size_bytes
            / (1024 * 1024)
        )

        print(f"Source:       {file_result.source_filename}")
        print(f"Parquet:      {file_result.parquet_filename}")
        print(f"Records:      {file_result.record_count:,}")
        print(f"Row groups:   {file_result.row_group_count:,}")
        print(f"Output size:  {size_mib:,.2f} MiB")
        print(
            "Output SHA:   "
            f"{file_result.output_sha256}"
        )
        print("-" * 60)

    print(f"Manifest: {result.manifest_path}")


if __name__ == "__main__":
    main()