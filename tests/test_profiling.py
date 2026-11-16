import pytest

from a1.data.profiling import (
    profile_dataset,
    write_profile_reports,
)
from a1.data.schema import (
    FeatureDefinition,
)


def test_profile_dataset_detects_data_quality_issues(
    tmp_path,
) -> None:
    """Check missing, invalid, binary, and timestamp values."""

    features = (
        FeatureDefinition(
            name="label",
            feature_type="binary",
            description="Binary target.",
        ),
        FeatureDefinition(
            name="attack_cat",
            feature_type="nominal",
            description="Attack category.",
        ),
        FeatureDefinition(
            name="stime",
            feature_type="timestamp",
            description="Start time.",
        ),
        FeatureDefinition(
            name="ltime",
            feature_type="timestamp",
            description="Last time.",
        ),
        FeatureDefinition(
            name="sport",
            feature_type="integer",
            description="Source port.",
        ),
        FeatureDefinition(
            name="dur",
            feature_type="float",
            description="Duration.",
        ),
        FeatureDefinition(
            name="is_sm_ips_ports",
            feature_type="binary",
            description="Same IP and port indicator.",
        ),
        FeatureDefinition(
            name="is_ftp_login",
            feature_type="binary",
            description="FTP login indicator.",
        ),
    )

    csv_path = tmp_path / "sample.csv"

    csv_path.write_text(
        "0,,100,100,80,0.5,0,0\n"
        "1,Fuzzers,200,199,81,1.25,1,4\n"
        "1,,bad,300,not-a-number,2.0,2,0\n",
        encoding="utf-8",
    )

    report = profile_dataset(
        data_directory=tmp_path,
        feature_definitions=features,
        data_filenames=("sample.csv",),
        chunk_size=2,
    )

    assert report["totals"]["records"] == 3

    assert report["missing_values"]["attack_cat"] == 2

    assert (
        report["numeric_validation"]["sport"][
            "invalid_numeric_values"
        ]
        == 1
    )

    assert (
        report["numeric_validation"]["is_sm_ips_ports"][
            "binary_domain_violations"
        ]
        == 1
    )

    assert (
        report["numeric_validation"]["is_ftp_login"][
            "binary_domain_violations"
        ]
        == 1
    )

    assert (
        report["timestamp_validation"][
            "rows_where_ltime_precedes_stime"
        ]
        == 1
    )

    label_category_counts = {
        (
            row["label"],
            row["attack_cat"],
        ): row["records"]
        for row in report["label_attack_category_counts"]
    }

    assert label_category_counts == {
        ("0", None): 1,
        ("1", None): 1,
        ("1", "Fuzzers"): 1,
    }

    assert (
        report["category_counts"]["attack_cat"]["Fuzzers"]
        == 1
    )

    output_directory = tmp_path / "reports"

    output_paths = write_profile_reports(
        report=report,
        output_directory=output_directory,
    )

    assert len(output_paths) == 8

    for output_path in output_paths.values():
        assert output_path.is_file()


def test_profile_dataset_rejects_invalid_chunk_size(
    tmp_path,
) -> None:
    """The profiler should reject a zero-sized chunk."""

    features = (
        FeatureDefinition(
            name="label",
            feature_type="binary",
            description="Binary target.",
        ),
        FeatureDefinition(
            name="attack_cat",
            feature_type="nominal",
            description="Attack category.",
        ),
        FeatureDefinition(
            name="stime",
            feature_type="timestamp",
            description="Start time.",
        ),
        FeatureDefinition(
            name="ltime",
            feature_type="timestamp",
            description="Last time.",
        ),
    )

    with pytest.raises(
        ValueError,
        match="chunk_size",
    ):

        profile_dataset(
            data_directory=tmp_path,
            feature_definitions=features,
            data_filenames=("sample.csv",),
            chunk_size=0,
        )


def test_profile_dataset_parses_hexadecimal_port_values(
    tmp_path,
) -> None:
    """Test hexadecimal values and protocol-specific port handling."""

    features = (
        FeatureDefinition(
            name="label",
            feature_type="binary",
            description="Binary target.",
        ),
        FeatureDefinition(
            name="attack_cat",
            feature_type="nominal",
            description="Attack category.",
        ),
        FeatureDefinition(
            name="stime",
            feature_type="timestamp",
            description="Start time.",
        ),
        FeatureDefinition(
            name="ltime",
            feature_type="timestamp",
            description="Last time.",
        ),
        FeatureDefinition(
            name="proto",
            feature_type="nominal",
            description="Protocol.",
        ),
        FeatureDefinition(
            name="sport",
            feature_type="integer",
            description="Source port.",
        ),
        FeatureDefinition(
            name="dsport",
            feature_type="integer",
            description="Destination port.",
        ),
        FeatureDefinition(
            name="is_ftp_login",
            feature_type="binary",
            description="FTP login indicator.",
        ),
        FeatureDefinition(
            name="ct_ftp_cmd",
            feature_type="integer",
            description="FTP command count.",
        ),
        FeatureDefinition(
            name="service",
            feature_type="nominal",
            description="Network service.",
        ),
        FeatureDefinition(
            name="state",
            feature_type="nominal",
            description="Connection state.",
        ),
    )

    csv_path = tmp_path / "sample.csv"

    csv_path.write_text(
        "0,,100,100,icmp,0xc0a8,0xcc09,,,-,URH\n"
        "0,,100,100,esp,-,0x20205321,,,-,INT\n"
        "1, Fuzzers ,100,100,tcp,80,443,2,2,ftp,FIN\n",
        encoding="utf-8",
    )

    report = profile_dataset(
        data_directory=tmp_path,
        feature_definitions=features,
        data_filenames=("sample.csv",),
        chunk_size=2,
    )

    assert report["totals"]["records"] == 3

    sport_numeric = report["numeric_validation"]["sport"]
    dsport_numeric = report["numeric_validation"]["dsport"]

    assert sport_numeric["invalid_numeric_values"] == 0
    assert dsport_numeric["invalid_numeric_values"] == 0

    assert sport_numeric["hexadecimal_values"] == 1
    assert dsport_numeric["hexadecimal_values"] == 2

    assert sport_numeric["sentinel_values"] == 1
    assert dsport_numeric["sentinel_values"] == 0

    sport_report = (
        report["port_field_analysis"]["features"]["sport"]
    )

    dsport_report = (
        report["port_field_analysis"]["features"]["dsport"]
    )

    assert sport_report["dash_sentinel_values"] == 1
    assert dsport_report["dash_sentinel_values"] == 0

    assert sport_report["transport_protocol_numeric_values"] == 1
    assert dsport_report["transport_protocol_numeric_values"] == 1

    assert sport_report["transport_protocol_out_of_range_values"] == 0
    assert dsport_report["transport_protocol_out_of_range_values"] == 0

    assert sport_report["non_port_protocol_numeric_values"] == 1
    assert dsport_report["non_port_protocol_numeric_values"] == 2

    special_contexts = (
        report["port_field_analysis"]["special_value_contexts"]
    )

    assert len(special_contexts) == 4

    ftp_report = report["ftp_login_domain_analysis"]

    assert ftp_report["out_of_domain_records"] == 1

    assert ftp_report["out_of_domain_value_counts"] == {
        "2": 1,
    }

    assert (
        ftp_report["out_of_domain_records_equal_ct_ftp_cmd"]
        == 1
    )

    assert (
        ftp_report["context_counts"][0]["attack_cat"]
        == "Fuzzers"
    )

    label_category_counts = {
        (
            row["label"],
            row["attack_cat"],
        ): row["records"]
        for row in report["label_attack_category_counts"]
    }

    assert label_category_counts == {
        ("0", None): 2,
        ("1", "Fuzzers"): 1,
    }

    output_directory = tmp_path / "reports"

    output_paths = write_profile_reports(
        report=report,
        output_directory=output_directory,
    )

    assert len(output_paths) == 8

    assert "port_validation" in output_paths
    assert "port_special_value_contexts" in output_paths
    assert "ftp_login_anomalies" in output_paths

    for output_path in output_paths.values():
        assert output_path.is_file()