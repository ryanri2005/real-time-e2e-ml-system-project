import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from a1.data.schema import (
    DATA_FILENAMES,
    FeatureDefinition,
)

NUMERIC_TYPES = {
    "integer",
    "float",
    "timestamp",
    "binary",
}

INTEGER_LIKE_TYPES = {
    "integer",
    "timestamp",
    "binary",
}

PORT_COLUMNS = ("sport", "dsport")

PORT_NUMBER_PROTOCOLS = {
    "tcp",
    "udp",
    "sctp",
    "dccp",
}

CATEGORY_COLUMNS = (
    "proto",
    "state",
    "service",
    "attack_cat",
    "label",
    "is_sm_ips_ports",
    "is_ftp_login",
)

REQUIRED_PROFILE_COLUMNS = {
    "label",
    "attack_cat",
    "stime",
    "ltime",
}


def _parse_numeric_values(
    feature_name: str,
    values: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Parse numeric values, including hexadecimal port-field values."""

    values = values.str.strip()

    sentinel_mask = pd.Series(
        False,
        index=values.index,
        dtype=bool,
    )

    hexadecimal_mask = pd.Series(
        False,
        index=values.index,
        dtype=bool,
    )

    normalized_values = values.copy()

    if feature_name in PORT_COLUMNS:

        sentinel_mask = values.eq("-")

        hexadecimal_mask = (
            values.str.fullmatch(
                r"0[xX][0-9a-fA-F]+"
            )
            .fillna(False)
        )

        if hexadecimal_mask.any():

            normalized_values.loc[hexadecimal_mask] = (
                values.loc[hexadecimal_mask].map(
                    lambda value: str(int(value, 16))
                )
            )

        normalized_values = normalized_values.mask(
            sentinel_mask
        )

    numeric_values = pd.to_numeric(
        normalized_values,
        errors="coerce",
    )

    return (
        numeric_values,
        sentinel_mask,
        hexadecimal_mask,
    )


def _epoch_to_iso8601(
    epoch_seconds: float | None,
) -> str | None:
    """Convert Unix epoch seconds into a UTC ISO timestamp."""

    if epoch_seconds is None:
        return None

    timestamp = pd.to_datetime(
        epoch_seconds,
        unit="s",
        utc=True,
        errors="coerce",
    )

    if pd.isna(timestamp):
        return None

    return timestamp.isoformat()


def profile_dataset(
    data_directory: Path,
    feature_definitions: tuple[FeatureDefinition, ...],
    data_filenames: tuple[str, ...] = DATA_FILENAMES,
    chunk_size: int = 50_000,
) -> dict[str, Any]:
    """Profile the dataset without loading all records into memory."""

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero."
        )

    if not feature_definitions:
        raise ValueError(
            "At least one feature definition is required."
        )

    if not data_filenames:
        raise ValueError(
            "At least one data filename is required."
        )

    feature_names = [
        feature.name
        for feature in feature_definitions
    ]

    feature_name_set = set(feature_names)

    if len(feature_names) != len(feature_name_set):
        raise ValueError(
            "Duplicate feature names were provided."
        )

    missing_required_columns = (
        REQUIRED_PROFILE_COLUMNS - feature_name_set
    )

    if missing_required_columns:
        raise ValueError(
            "Required profiling columns are missing: "
            f"{sorted(missing_required_columns)}"
        )

    for filename in data_filenames:

        file_path = data_directory / filename

        if not file_path.is_file():
            raise FileNotFoundError(
                f"Dataset file not found: {file_path}"
            )

    metadata_type_counts = Counter(
        feature.feature_type
        for feature in feature_definitions
    )

    missing_counts = {
        name: 0
        for name in feature_names
    }

    category_columns = [
        name
        for name in CATEGORY_COLUMNS
        if name in feature_name_set
    ]

    category_counts = {
        name: Counter()
        for name in category_columns
    }

    numeric_stats = {}

    for feature in feature_definitions:

        if feature.feature_type not in NUMERIC_TYPES:
            continue

        numeric_stats[feature.name] = {
            "metadata_type": feature.feature_type,
            "non_missing_values": 0,
            "sentinel_values": 0,
            "hexadecimal_values": 0,
            "invalid_numeric_values": 0,
            "non_finite_values": 0,
            "fractional_values": 0,
            "negative_values": 0,
            "binary_domain_violations": 0,
            "unexpected_binary_values": Counter(),
            "minimum": None,
            "maximum": None,
        }

    port_feature_names = [
        name
        for name in PORT_COLUMNS
        if name in feature_name_set
    ]

    port_stats = {
        name: {
            "hexadecimal_values": 0,
            "dash_sentinel_values": 0,
            "numeric_values": 0,
            "transport_protocol_numeric_values": 0,
            "transport_protocol_unparsed_values": 0,
            "transport_protocol_non_finite_values": 0,
            "transport_protocol_out_of_range_values": 0,
            "non_port_protocol_numeric_values": 0,
            "non_port_protocol_counts": Counter(),
        }
        for name in port_feature_names
    }

    port_special_context_counts = Counter()

    ftp_context_columns = [
        name
        for name in (
            "is_ftp_login",
            "ct_ftp_cmd",
            "proto",
            "service",
            "state",
            "attack_cat",
            "label",
        )
        if name in feature_name_set
    ]

    ftp_login_out_of_domain_values = Counter()
    ftp_login_out_of_domain_contexts = Counter()

    ftp_login_out_of_domain_records_equal_ct_ftp_cmd = 0

    file_results = []

    total_records = 0
    ltime_before_stime = 0

    label_category_counts = Counter()

    for filename in data_filenames:

        file_path = data_directory / filename
        file_records = 0

        print(f"\nProfiling: {filename}")

        try:

            chunks = pd.read_csv(
                file_path,
                header=None,
                names=feature_names,
                dtype="string",
                keep_default_na=False,
                na_filter=False,
                chunksize=chunk_size,
                encoding="utf-8-sig",
                on_bad_lines="error",
            )

            for chunk in chunks:

                file_records += len(chunk)

                normalized_cross_values = {}
                timestamp_values = {}

                numeric_values_by_feature = {}
                sentinel_masks_by_feature = {}
                hexadecimal_masks_by_feature = {}

                # Inspect each feature according to its metadata type.
                for feature in feature_definitions:

                    name = feature.name

                    values = chunk[name].str.strip()

                    missing_mask = values.eq("")

                    missing_counts[name] += int(
                        missing_mask.sum()
                    )

                    if name in category_counts:

                        non_missing_categories = values.loc[
                            ~missing_mask
                        ]

                        observed_counts = (
                            non_missing_categories.value_counts()
                        )

                        for category, count in observed_counts.items():

                            category_counts[name][str(category)] += int(
                                count
                            )

                    if name in {"label", "attack_cat"}:

                        normalized_cross_values[name] = (
                            values.mask(
                                missing_mask,
                                "",
                            )
                        )

                    if feature.feature_type not in NUMERIC_TYPES:
                        continue

                    (
                        numeric_values,
                        sentinel_mask,
                        hexadecimal_mask,
                    ) = _parse_numeric_values(
                        name,
                        values,
                    )

                    numeric_values_by_feature[name] = numeric_values

                    sentinel_masks_by_feature[name] = sentinel_mask

                    hexadecimal_masks_by_feature[name] = (
                        hexadecimal_mask
                    )

                    stats = numeric_stats[name]

                    stats["sentinel_values"] += int(
                        sentinel_mask.sum()
                    )

                    stats["hexadecimal_values"] += int(
                        hexadecimal_mask.sum()
                    )

                    if name in PORT_COLUMNS:

                        port_stats[name]["dash_sentinel_values"] += int(
                            sentinel_mask.sum()
                        )

                        port_stats[name]["hexadecimal_values"] += int(
                            hexadecimal_mask.sum()
                        )

                    non_missing_mask = (
                        ~missing_mask & ~sentinel_mask
                    )

                    stats["non_missing_values"] += int(
                        non_missing_mask.sum()
                    )

                    invalid_mask = (
                        non_missing_mask
                        & numeric_values.isna()
                    )

                    stats["invalid_numeric_values"] += int(
                        invalid_mask.sum()
                    )

                    parsed_mask = (
                        non_missing_mask
                        & numeric_values.notna()
                    )

                    observed_values = (
                        numeric_values.loc[parsed_mask]
                        .to_numpy(
                            dtype=np.float64,
                            na_value=np.nan,
                        )
                    )

                    finite_mask = np.isfinite(
                        observed_values
                    )

                    stats["non_finite_values"] += int(
                        (~finite_mask).sum()
                    )

                    finite_values = observed_values[finite_mask]

                    if finite_values.size > 0:

                        stats["negative_values"] += int(
                            (finite_values < 0).sum()
                        )

                        if feature.feature_type in INTEGER_LIKE_TYPES:

                            fractional_mask = (
                                finite_values
                                != np.trunc(finite_values)
                            )

                            stats["fractional_values"] += int(
                                fractional_mask.sum()
                            )

                        observed_minimum = float(
                            finite_values.min()
                        )

                        observed_maximum = float(
                            finite_values.max()
                        )

                        if stats["minimum"] is None:

                            stats["minimum"] = observed_minimum

                        else:

                            stats["minimum"] = min(
                                stats["minimum"],
                                observed_minimum,
                            )

                        if stats["maximum"] is None:

                            stats["maximum"] = observed_maximum

                        else:

                            stats["maximum"] = max(
                                stats["maximum"],
                                observed_maximum,
                            )

                        if feature.feature_type == "binary":

                            unexpected_values = finite_values[
                                ~np.isin(
                                    finite_values,
                                    [0.0, 1.0],
                                )
                            ]

                            stats["binary_domain_violations"] += int(
                                unexpected_values.size
                            )

                            if unexpected_values.size > 0:

                                distinct_values, value_counts = np.unique(
                                    unexpected_values,
                                    return_counts=True,
                                )

                                for value, count in zip(
                                    distinct_values,
                                    value_counts,
                                ):

                                    value_label = format(
                                        float(value),
                                        ".15g",
                                    )

                                    stats[
                                        "unexpected_binary_values"
                                    ][value_label] += int(count)

                    if name in {"stime", "ltime"}:

                        timestamp_values[name] = (
                            numeric_values.to_numpy(
                                dtype=np.float64,
                                na_value=np.nan,
                            )
                        )

                # Count the relationship between binary labels
                # and attack categories, including missing categories.
                if (
                    "label" in normalized_cross_values
                    and "attack_cat" in normalized_cross_values
                ):

                    cross_frame = pd.DataFrame({
                        "label": normalized_cross_values["label"],
                        "attack_cat": normalized_cross_values["attack_cat"],
                    })

                    cross_counts = cross_frame.value_counts(
                        sort=False,
                        dropna=False,
                    )

                    for pair, count in cross_counts.items():

                        label_value = str(pair[0])
                        category_value = str(pair[1])

                        label_category_counts[
                            (label_value, category_value)
                        ] += int(count)

                # Evaluate port-like fields in the context of their protocol.
                if (
                    "proto" in feature_name_set
                    and port_feature_names
                ):

                    protocol_values = (
                        chunk["proto"]
                        .str.strip()
                        .str.lower()
                    )

                    transport_protocol_mask = (
                        protocol_values.isin(
                            PORT_NUMBER_PROTOCOLS
                        ).to_numpy(dtype=bool)
                    )

                    for name in port_feature_names:

                        raw_values = chunk[name].str.strip()

                        numeric_values = (
                            numeric_values_by_feature[name]
                        )

                        sentinel_mask = (
                            sentinel_masks_by_feature[name]
                        )

                        hexadecimal_mask = (
                            hexadecimal_masks_by_feature[name]
                        )

                        numeric_array = numeric_values.to_numpy(
                            dtype=np.float64,
                            na_value=np.nan,
                        )

                        blank_array = raw_values.eq("").to_numpy(
                            dtype=bool
                        )

                        sentinel_array = sentinel_mask.to_numpy(
                            dtype=bool
                        )

                        numeric_is_missing = (
                            numeric_values.isna().to_numpy(
                                dtype=bool
                            )
                        )

                        hexadecimal_array = (
                            hexadecimal_mask.to_numpy(
                                dtype=bool
                            )
                        )

                        finite_array = np.isfinite(numeric_array)

                        parsed_array = (
                            ~blank_array
                            & ~sentinel_array
                            & ~numeric_is_missing
                        )

                        finite_numeric_mask = (
                            parsed_array & finite_array
                        )

                        non_finite_numeric_mask = (
                            parsed_array & ~finite_array
                        )

                        invalid_numeric_mask = (
                            ~blank_array
                            & ~sentinel_array
                            & numeric_is_missing
                        )

                        port_feature_stats = port_stats[name]

                        port_feature_stats["numeric_values"] += int(
                            finite_numeric_mask.sum()
                        )

                        transport_numeric_mask = (
                            finite_numeric_mask
                            & transport_protocol_mask
                        )

                        non_port_numeric_mask = (
                            finite_numeric_mask
                            & ~transport_protocol_mask
                        )

                        port_feature_stats[
                            "transport_protocol_numeric_values"
                        ] += int(
                            transport_numeric_mask.sum()
                        )

                        port_feature_stats[
                            "non_port_protocol_numeric_values"
                        ] += int(
                            non_port_numeric_mask.sum()
                        )

                        transport_unparsed_mask = (
                            invalid_numeric_mask
                            & transport_protocol_mask
                        )

                        port_feature_stats[
                            "transport_protocol_unparsed_values"
                        ] += int(
                            transport_unparsed_mask.sum()
                        )

                        transport_non_finite_mask = (
                            non_finite_numeric_mask
                            & transport_protocol_mask
                        )

                        port_feature_stats[
                            "transport_protocol_non_finite_values"
                        ] += int(
                            transport_non_finite_mask.sum()
                        )

                        out_of_range_mask = (
                            transport_numeric_mask
                            & (
                                (numeric_array < 0)
                                | (numeric_array > 65535)
                            )
                        )

                        port_feature_stats[
                            "transport_protocol_out_of_range_values"
                        ] += int(
                            out_of_range_mask.sum()
                        )

                        for protocol, count in (
                            protocol_values.loc[
                                non_port_numeric_mask
                            ]
                            .value_counts()
                            .items()
                        ):

                            port_feature_stats[
                                "non_port_protocol_counts"
                            ][str(protocol)] += int(count)

                        special_value_mask = (
                            sentinel_array
                            | hexadecimal_array
                        )

                        special_protocols = (
                            protocol_values.loc[
                                special_value_mask
                            ].tolist()
                        )

                        special_values = (
                            raw_values.loc[
                                special_value_mask
                            ].str.lower().tolist()
                        )

                        for protocol, raw_value in zip(
                            special_protocols,
                            special_values,
                        ):

                            port_special_context_counts[
                                (
                                    name,
                                    str(protocol),
                                    str(raw_value),
                                )
                            ] += 1

                # Investigate is_ftp_login values outside its binary domain.
                if {
                    "is_ftp_login",
                    "ct_ftp_cmd",
                }.issubset(feature_name_set):

                    ftp_values = (
                        chunk["is_ftp_login"].str.strip()
                    )

                    ftp_numeric_values = pd.to_numeric(
                        ftp_values,
                        errors="coerce",
                    )

                    ftp_array = ftp_numeric_values.to_numpy(
                        dtype=np.float64,
                        na_value=np.nan,
                    )

                    finite_ftp_mask = np.isfinite(ftp_array)

                    nonbinary_mask = (
                        finite_ftp_mask
                        & ~np.isin(
                            ftp_array,
                            [0.0, 1.0],
                        )
                    )

                    selected_context = chunk.loc[
                        nonbinary_mask,
                        ftp_context_columns,
                    ].copy()

                    for column in ftp_context_columns:

                        selected_context[column] = (
                            selected_context[column].str.strip()
                        )

                    for record in selected_context.itertuples(
                        index=False,
                        name=None,
                    ):

                        context = dict(
                            zip(
                                ftp_context_columns,
                                record,
                            )
                        )

                        ftp_value = context["is_ftp_login"]

                        command_value = context["ct_ftp_cmd"]

                        ftp_login_out_of_domain_values[
                            ftp_value
                        ] += 1

                        if ftp_value == command_value:

                            ftp_login_out_of_domain_records_equal_ct_ftp_cmd += 1

                        context_key = tuple(
                            str(context[column])
                            for column in ftp_context_columns
                        )

                        ftp_login_out_of_domain_contexts[
                            context_key
                        ] += 1

                # Compare the start and last timestamps in each record.
                if (
                    "stime" in timestamp_values
                    and "ltime" in timestamp_values
                ):

                    start_times = timestamp_values["stime"]
                    end_times = timestamp_values["ltime"]

                    valid_pairs = (
                        np.isfinite(start_times)
                        & np.isfinite(end_times)
                    )

                    ltime_before_stime += int(
                        (
                            end_times[valid_pairs]
                            < start_times[valid_pairs]
                        ).sum()
                    )

        except pd.errors.ParserError as error:

            raise ValueError(
                f"CSV parsing failed for {file_path}: {error}"
            ) from error

        except pd.errors.EmptyDataError as error:

            raise ValueError(
                f"Dataset file is empty: {file_path}"
            ) from error

        total_records += file_records

        file_results.append({
            "filename": filename,
            "records": file_records,
            "size_bytes": file_path.stat().st_size,
        })

        print(f"Records processed: {file_records:,}")

    # Convert numeric results into JSON-compatible dictionaries.
    numeric_profile = {}

    for name, stats in numeric_stats.items():

        unexpected_values = stats["unexpected_binary_values"]

        numeric_profile[name] = {
            **{
                key: value
                for key, value in stats.items()
                if key != "unexpected_binary_values"
            },
            "unexpected_binary_values": dict(
                sorted(unexpected_values.items())
            ),
        }

    missing_fractions = {}

    for name in feature_names:

        if total_records == 0:

            missing_fractions[name] = 0.0

        else:

            missing_fractions[name] = (
                missing_counts[name] / total_records
            )

    timestamp_profile = {}

    for name in ("stime", "ltime"):

        stats = numeric_profile[name]

        timestamp_profile[name] = {
            "metadata_type": "timestamp",
            "missing_values": missing_counts[name],
            "invalid_numeric_values": (
                stats["invalid_numeric_values"]
            ),
            "minimum_epoch_seconds": stats["minimum"],
            "maximum_epoch_seconds": stats["maximum"],
            "earliest_utc": _epoch_to_iso8601(
                stats["minimum"]
            ),
            "latest_utc": _epoch_to_iso8601(
                stats["maximum"]
            ),
        }

    label_category_rows = []

    for (label_value, category_value), count in sorted(
        label_category_counts.items()
    ):

        label_category_rows.append({
            "label": label_value,
            "attack_cat": (
                None if category_value == "" else category_value
            ),
            "records": int(count),
        })

    port_feature_profiles = {}

    for name, stats in port_stats.items():

        port_feature_profiles[name] = {
            **{
                key: value
                for key, value in stats.items()
                if key != "non_port_protocol_counts"
            },
            "non_port_protocol_counts": dict(
                sorted(
                    stats["non_port_protocol_counts"].items()
                )
            ),
        }

    port_special_context_rows = []

    for (feature, protocol, raw_value), count in sorted(
        port_special_context_counts.items()
    ):

        port_special_context_rows.append({
            "feature": feature,
            "protocol": protocol,
            "raw_value": raw_value,
            "records": int(count),
        })

    ftp_login_context_rows = []

    for context_key, count in sorted(
        ftp_login_out_of_domain_contexts.items()
    ):

        context_row = dict(
            zip(
                ftp_context_columns,
                context_key,
            )
        )

        context_row["records"] = int(count)

        ftp_login_context_rows.append(context_row)

    ftp_login_domain_profile = {
        "out_of_domain_records": int(
            sum(ftp_login_out_of_domain_values.values())
        ),
        "out_of_domain_value_counts": dict(
            sorted(ftp_login_out_of_domain_values.items())
        ),
        "out_of_domain_records_equal_ct_ftp_cmd": (
            ftp_login_out_of_domain_records_equal_ct_ftp_cmd
        ),
        "context_columns": ftp_context_columns,
        "context_counts": ftp_login_context_rows,
    }

    report = {
        "dataset": "UNSW-NB15",
        "generated_at_utc": datetime.now(
            UTC
        ).isoformat(),
        "schema": {
            "feature_count": len(feature_definitions),
            "feature_type_counts": dict(
                sorted(metadata_type_counts.items())
            ),
            "features": [
                {
                    "name": feature.name,
                    "type": feature.feature_type,
                    "description": feature.description,
                }
                for feature in feature_definitions
            ],
        },
        "files": file_results,
        "totals": {
            "records": total_records,
            "files": len(file_results),
        },
        "missing_values": missing_counts,
        "missing_fractions": missing_fractions,
        "numeric_validation": numeric_profile,
        "category_counts": {
            name: dict(sorted(counts.items()))
            for name, counts in category_counts.items()
        },
        "label_attack_category_counts": label_category_rows,
        "timestamp_validation": {
            "features": timestamp_profile,
            "rows_where_ltime_precedes_stime": (
                ltime_before_stime
            ),
        },
        "port_field_analysis": {
            "range_checked_protocols": sorted(
                PORT_NUMBER_PROTOCOLS
            ),
            "features": port_feature_profiles,
            "special_value_contexts": (
                port_special_context_rows
            ),
        },
        "ftp_login_domain_analysis": ftp_login_domain_profile,
        "notes": [
            (
                "Empty and whitespace-only fields are counted as missing."
            ),
            (
                "For sport and dsport, the literal '-' is reported "
                "separately as a sentinel value."
            ),
            (
                "Hexadecimal sport and dsport values are parsed "
                "as base-16 integers for profiling."
            ),
            (
                "The 16-bit port range is checked only for TCP, UDP, "
                "SCTP, and DCCP records."
            ),
            (
                "Values outside a binary feature's documented domain "
                "are reported but not modified."
            ),
            (
                "is_ftp_login values outside 0 and 1 are compared "
                "with ct_ftp_cmd."
            ),
            (
                "Duplicate-record analysis is performed separately."
            ),
            (
                "Original CSV files are read only and are not modified."
            ),
        ],
    }

    return report


def write_profile_reports(
    report: dict[str, Any],
    output_directory: Path,
) -> dict[str, Path]:
    """Write the profiling results as JSON and CSV reports."""

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = (
        output_directory / "unsw_nb15_profile.json"
    )

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # Missing-value report.
    missing_rows = []

    for feature in report["schema"]["features"]:

        name = feature["name"]
        missing_count = report["missing_values"][name]

        missing_rows.append({
            "feature": name,
            "metadata_type": feature["type"],
            "missing_count": missing_count,
            "missing_fraction": (
                report["missing_fractions"][name]
            ),
        })

    missing_csv_path = (
        output_directory / "unsw_nb15_missing_values.csv"
    )

    pd.DataFrame(missing_rows).to_csv(
        missing_csv_path,
        index=False,
        encoding="utf-8",
    )

    # Numeric validation report.
    numeric_rows = []

    for name, stats in report["numeric_validation"].items():

        numeric_rows.append({
            "feature": name,
            "metadata_type": stats["metadata_type"],
            "non_missing_values": stats["non_missing_values"],
            "sentinel_values": stats["sentinel_values"],
            "hexadecimal_values": stats["hexadecimal_values"],
            "invalid_numeric_values": stats["invalid_numeric_values"],
            "non_finite_values": stats["non_finite_values"],
            "fractional_values": stats["fractional_values"],
            "negative_values": stats["negative_values"],
            "binary_domain_violations": stats[
                "binary_domain_violations"
            ],
            "minimum": stats["minimum"],
            "maximum": stats["maximum"],
        })

    numeric_csv_path = (
        output_directory / "unsw_nb15_numeric_validation.csv"
    )

    pd.DataFrame(numeric_rows).to_csv(
        numeric_csv_path,
        index=False,
        encoding="utf-8",
    )

    # Categorical-value report.
    category_rows = []

    for feature, counts in report["category_counts"].items():

        for category, count in counts.items():

            category_rows.append({
                "feature": feature,
                "value": category,
                "count": count,
            })

    category_csv_path = (
        output_directory / "unsw_nb15_category_counts.csv"
    )

    pd.DataFrame(
        category_rows,
        columns=["feature", "value", "count"],
    ).to_csv(
        category_csv_path,
        index=False,
        encoding="utf-8",
    )

    # Binary-label and attack-category relationship.
    label_category_csv_path = (
        output_directory / "unsw_nb15_label_attack_category.csv"
    )

    pd.DataFrame(
        report["label_attack_category_counts"],
        columns=["label", "attack_cat", "records"],
    ).to_csv(
        label_category_csv_path,
        index=False,
        encoding="utf-8",
    )

    # Protocol-aware port-field report.
    port_rows = []

    for feature, stats in (
        report["port_field_analysis"]["features"].items()
    ):

        port_rows.append({
            "feature": feature,
            "hexadecimal_values": stats["hexadecimal_values"],
            "dash_sentinel_values": stats["dash_sentinel_values"],
            "numeric_values": stats["numeric_values"],
            "transport_protocol_numeric_values": stats[
                "transport_protocol_numeric_values"
            ],
            "transport_protocol_unparsed_values": stats[
                "transport_protocol_unparsed_values"
            ],
            "transport_protocol_non_finite_values": stats[
                "transport_protocol_non_finite_values"
            ],
            "transport_protocol_out_of_range_values": stats[
                "transport_protocol_out_of_range_values"
            ],
            "non_port_protocol_numeric_values": stats[
                "non_port_protocol_numeric_values"
            ],
        })

    port_csv_path = (
        output_directory / "unsw_nb15_port_validation.csv"
    )

    pd.DataFrame(
        port_rows,
        columns=[
            "feature",
            "hexadecimal_values",
            "dash_sentinel_values",
            "numeric_values",
            "transport_protocol_numeric_values",
            "transport_protocol_unparsed_values",
            "transport_protocol_non_finite_values",
            "transport_protocol_out_of_range_values",
            "non_port_protocol_numeric_values",
        ],
    ).to_csv(
        port_csv_path,
        index=False,
        encoding="utf-8",
    )

    # Special port-field values grouped by protocol.
    port_context_csv_path = (
        output_directory / "unsw_nb15_port_special_value_contexts.csv"
    )

    pd.DataFrame(
        report["port_field_analysis"]["special_value_contexts"],
        columns=[
            "feature",
            "protocol",
            "raw_value",
            "records",
        ],
    ).to_csv(
        port_context_csv_path,
        index=False,
        encoding="utf-8",
    )

    # is_ftp_login values outside the documented binary domain.
    ftp_context_columns = (
        report["ftp_login_domain_analysis"]["context_columns"]
    )

    ftp_csv_path = (
        output_directory / "unsw_nb15_ftp_login_anomalies.csv"
    )

    pd.DataFrame(
        report["ftp_login_domain_analysis"]["context_counts"],
        columns=[
            *ftp_context_columns,
            "records",
        ],
    ).to_csv(
        ftp_csv_path,
        index=False,
        encoding="utf-8",
    )

    return {
        "json": json_path,
        "missing_values": missing_csv_path,
        "numeric_validation": numeric_csv_path,
        "category_counts": category_csv_path,
        "label_attack_category": label_category_csv_path,
        "port_validation": port_csv_path,
        "port_special_value_contexts": port_context_csv_path,
        "ftp_login_anomalies": ftp_csv_path,
    }