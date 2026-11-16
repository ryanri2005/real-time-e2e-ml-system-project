
# UNSW-NB15 Data Quality and Preprocessing Specification

## 1. Purpose

This document records the results of full-dataset structural validation, data-quality profiling, and exact duplicate analysis for the locally downloaded UNSW-NB15 dataset.

It establishes the current data-handling decisions and requirements for subsequent data engineering, feature engineering, model training, and temporal evaluation.

The purpose is to maintain a reproducible and auditable processing pipeline.

**Important:** This document describes the observed raw data and the current preprocessing policy. It does not claim that all cleaning and transformation decisions have been implemented in the production data pipeline.

No original CSV records have been modified or removed.

## 2. Dataset audit scope

The audit covers all four original CSV files and all 49 fields.

| File | Records |
|---|---:|
| `UNSW-NB15_1.csv` | 700,001 |
| `UNSW-NB15_2.csv` | 700,001 |
| `UNSW-NB15_3.csv` | 700,001 |
| `UNSW-NB15_4.csv` | 440,044 |
| **Total** | **2,540,047** |

The official UNSW dataset page reports 2,540,044 records. The locally inspected dataset contains 2,540,047 records. This difference of three records remains unresolved and is documented in `unsw_nb15.md`.

The observed local record count is used when validating this particular downloaded dataset.

### 2.1 Validation methodology

The following components were implemented:

| Component | Implementation |
|---|---|
| Dataset inspection | Chunked pandas inspection |
| Feature schema | Metadata-driven feature definitions |
| CSV structural validation | Python CSV parser |
| Data-quality profiling | Chunked pandas processing |
| Duplicate analysis | SHA-256 fingerprints and SQLite |

The profiler processes records in chunks of 50,000.

The duplicate-analysis process uses a temporary SQLite database to avoid loading the complete dataset into memory.

The temporary database is removed after the duplicate reports have been generated.

## 3. Feature schema

The official metadata identifies 49 features.

| Feature type | Number |
|---|---:|
| Nominal | 6 |
| Integer | 28 |
| Float | 10 |
| Timestamp | 2 |
| Binary | 3 |
| **Total** | **49** |

Feature definitions are loaded from `NUSW-NB15_features.csv`.

The internal schema normalizes feature names by removing whitespace and converting names to lowercase.

For example:

`ct_src_ ltm` becomes `ct_src_ltm`.

This normalization applies to internal column names, not the original CSV records.

## 4. Structural validation results

All four original CSV files passed full-dataset structural validation.

| Measurement | Result |
|---|---:|
| Total data records | 2,540,047 |
| Expected fields per record | 49 |
| Valid records | 2,540,047 |
| Malformed records | 0 |
| Blank records | 0 |

Every record was checked against the expected 49-field structure.

The CSV files contain no header row and are parsed using the feature names loaded from the metadata.

**Result:** All four CSV files passed structural validation.

## 5. Missing-value analysis

The profiler identifies empty and whitespace-only fields as missing values.

The following features contained missing values:

| Feature | Missing records | Percentage |
|---|---:|---:|
| `ct_flw_http_mthd` | 1,348,145 | 53.0756% |
| `is_ftp_login` | 1,429,879 | 56.2934% |
| `ct_ftp_cmd` | 1,429,879 | 56.2934% |
| `attack_cat` | 2,218,764 | 87.3513% |

These are the features with reported blank values in the full-dataset profiling run.

### 5.1 Interpretation of missing attack categories

All 2,218,764 records with a missing `attack_cat` value have `label = 0`.

The benign records therefore have no attack category.

These missing values are consistent with the meaning of the target field.

**Decision:** Do not impute an attack category for benign records.

### 5.2 Other missing values

`ct_flw_http_mthd`, `is_ftp_login`, and `ct_ftp_cmd` contain substantial missingness.

The original values will be preserved.

The appropriate representation of missing values in derived model features will be determined during feature engineering and preprocessing implementation.

No arbitrary zero-filling or mean-imputation is applied at this stage.

### 5.3 The `-` value

The literal `-` is not treated as a universal missing-value indicator.

The feature metadata explicitly uses `-` for certain nominal features, including `service` and `state`.

For `sport` and `dsport`, `-` is recorded separately as a port-field sentinel.

The meaning of a value is determined using its feature definition and context.

## 6. Numeric-value validation

Numeric features were checked for:

- Invalid numeric representations.
- Non-finite values.
- Fractional values in integer-like fields.
- Negative values.
- Values outside documented binary domains.

After protocol-aware parsing of the port fields, the only reported binary-domain violation is `is_ftp_login`.

### 6.1 Port-field analysis

The metadata identifies `sport` and `dsport` as integer port fields.

However, some original values use hexadecimal notation or protocol-specific representations.

The full-dataset inspection found:

| Feature | Hexadecimal values | `-` sentinel values |
|---|---:|---:|
| `sport` | 6 | 2 |
| `dsport` | 297 | 7 |
| **Total** | **303** | **9** |

The hexadecimal values were parsed as base-16 integers for profiling.

All 303 hexadecimal observations and all nine dash sentinels were associated with ICMP or ESP records. The inspected records had binary label `0`.

The hexadecimal values included:

| Feature | Raw value | Occurrences |
|---|---|---:|
| `sport` | `0x000b` | 2 |
| `sport` | `0x000c` | 4 |
| `dsport` | `0xc0a8` | 54 |
| `dsport` | `0xcc09` | 241 |
| `dsport` | `0x20205321` | 2 |

The value `0x20205321` converts numerically to 538,989,345. This exceeds the ordinary 16-bit transport-port range, but both observations occur in ESP records.

Its exact protocol-specific meaning in this dataset has not been established.

The profiler therefore applies the 0–65,535 range check only to TCP, UDP, SCTP, and DCCP records.

Results:

| Measurement | `sport` | `dsport` |
|---|---:|---:|
| Invalid numeric strings after hexadecimal parsing | 0 | 0 |
| Unparsed values in checked transport protocols | 0 | 0 |
| Non-finite values in checked transport protocols | 0 | 0 |
| Out-of-range values in checked transport protocols | 0 | 0 |

**Current decision:**

- Preserve all original port-column strings in the raw data.
- Recognize hexadecimal notation during derived-data parsing.
- Treat `-` separately as a port-field sentinel.
- Do not apply ordinary transport-port semantics to ICMP or ESP values.
- Do not discard unusual records simply because their port-column representation is unexpected.

## 7. Binary-domain anomaly: `is_ftp_login`

The metadata defines `is_ftp_login` as a binary feature.

The actual distribution is:

| Raw value | Records |
|---|---:|
| Missing | 1,429,879 |
| 0 | 1,066,593 |
| 1 | 43,389 |
| 2 | 30 |
| 4 | 156 |
| **Total** | **2,540,047** |

There are 186 records with values outside the documented binary domain.

### 7.1 Context investigation

The full-dataset inspection established:

- All 30 records with value `2` have `ct_ftp_cmd = 2`.
- All 156 records with value `4` have `ct_ftp_cmd = 4`.
- All 186 records use TCP.
- The records have FTP-related service and command contexts, with two records using `service = -`.

The label breakdown is:

| `is_ftp_login` | Benign records | Malicious records |
|---|---:|---:|
| 2 | 22 | 8 |
| 4 | 140 | 16 |
| **Total** | **162** | **24** |

The values are correlated exactly with `ct_ftp_cmd` in these 186 records.

This is an observed relationship. It does not prove why the values occur or establish that they should be converted to 0 or 1.

**Current decision:**

- Preserve all original values.
- Record values outside 0 and 1 as binary-domain anomalies.
- Do not automatically convert 2 or 4 to zero or one.
- Investigate the effect of alternative representations during feature engineering and model evaluation.

## 8. Attack-category analysis

The binary label distribution is:

| Label | Records |
|---|---:|
| Benign (0) | 2,218,764 |
| Malicious (1) | 321,283 |
| **Total** | **2,540,047** |

The observed raw attack-category distribution is:

| Raw category | Records |
|---|---:|
| Analysis | 2,677 |
| Backdoor | 1,795 |
| Backdoors | 534 |
| DoS | 16,353 |
| Exploits | 44,525 |
| Fuzzers | 24,246 |
| Generic | 215,481 |
| Reconnaissance | 13,987 |
| Shellcode | 1,511 |
| Worms | 174 |

The dataset contains both `Backdoor` and `Backdoors`.

These are preserved as separate raw values in the current data-quality reports.

### 8.1 Target handling

`label` is the primary binary prediction target.

`attack_cat` is additional target information associated with malicious records.

It must not be included as an input feature when training a model to predict `label`, because doing so would expose information derived from the target and create target leakage.

Any normalization of `Backdoor` and `Backdoors` will be applied only in a documented derived category representation, while preserving the original value.

## 9. Timestamp validation

The timestamp fields are:

- `stime`: record start time.
- `ltime`: record last time.

The source values are Unix epoch timestamps in seconds.

Full-dataset results:

| Timestamp | Earliest UTC | Latest UTC |
|---|---|---|
| `stime` | 2015-01-22 11:49:37 | 2015-02-18 12:21:08 |
| `ltime` | 2015-01-22 11:50:14 | 2015-02-18 12:21:09 |

Validation results:

| Check | Result |
|---|---:|
| Invalid `stime` values | 0 |
| Invalid `ltime` values | 0 |
| Records where `ltime` precedes `stime` | 0 |

**Current decision:** Convert timestamps to a consistent UTC representation in derived data and use event time when building chronological training, validation, and test datasets.

Random splitting will not be used as a substitute for temporal evaluation.

## 10. Exact duplicate analysis

All 2,540,047 records were examined using exact record comparison.

### 10.1 Methodology

The duplicate analyzer:

1. Parses each CSV record into its 49 original field values.
2. Serializes every field with its UTF-8 byte length.
3. Calculates a SHA-256 fingerprint.
4. Uses a temporary SQLite database to track unique records and source locations.
5. Compares the complete serialized payload whenever an existing SHA-256 fingerprint is encountered.

The complete record comparison prevents different records from being classified as duplicates solely because of a hash collision.

No trimming, case conversion, whitespace normalization, or missing-value substitution is performed.

CSV quoting and line-ending differences do not create different records when their parsed field values are identical.

### 10.2 Duplicate results

| Measurement | Result |
|---|---:|
| Total records | 2,540,047 |
| Unique records | 2,059,414 |
| Duplicate groups | 88,210 |
| Records belonging to duplicate groups | 568,843 |
| Excess duplicate records | 480,633 |
| Duplicate groups with within-file repetitions | 88,207 |
| Duplicate groups occurring across files | 4 |
| Extra occurrences within individual files | 480,629 |
| Duplicate source locations recorded | 568,843 |

The within-file and cross-file group counts overlap.

The duplicate groups consist of:

- 88,206 groups with within-file repetitions only.
- 3 groups occurring across files only.
- 1 group having both within-file and cross-file repetitions.

The record-count reconciliation is:

`2,059,414 unique records + 480,633 excess duplicate records = 2,540,047 total records`

### 10.3 Duplicate-handling decision

No duplicate records have been deleted from the original dataset.

Exact duplicates may affect evaluation if identical observations are distributed across training and testing partitions.

During temporal splitting, duplicate groups will be examined to prevent exact duplicate observations from creating misleading evaluation results.

The decision to exclude, retain, or group repeated observations in derived datasets will be documented and supported by the evaluation design.

## 11. Current preprocessing policy

The following table separates established decisions from work that is not yet finalized.

| Area | Current decision |
|---|---|
| Raw records | Preserve all original records |
| CSV parsing | Use the metadata-defined 49-column schema |
| Missing values | Preserve raw fields; represent blanks explicitly in derived data |
| Nominal `-` markers | Preserve as meaningful categorical values where defined by metadata |
| Port-field `-` markers | Record separately as port-field sentinels |
| Hexadecimal port representations | Parse explicitly and preserve source representations |
| ICMP and ESP port-column values | Do not automatically interpret as ordinary transport ports |
| `is_ftp_login` values 2 and 4 | Preserve and flag; do not automatically recode |
| Missing `attack_cat` | Retain as missing for benign records |
| `Backdoor` / `Backdoors` | Preserve raw spellings; document any derived normalization |
| Exact duplicates | Retain until the evaluation and split policy is finalized |
| Timestamps | Preserve source values and use UTC representations in derived data |
| Binary target | Use `label` as the primary prediction target |

### 11.1 Requirements for derived data

Future ingestion and feature-engineering components must:

- Preserve the original source files.
- Keep transformations explicit and reproducible.
- Distinguish missing values from valid categorical markers.
- Avoid target leakage.
- Record any category normalization.
- Record how anomalous feature values are represented.
- Prevent duplicate leakage across evaluation partitions.
- Support chronological evaluation.
- Produce validation evidence for each generated dataset.

## 12. Open decisions before model training

The following items remain deliberately unresolved:

1. The three-record discrepancy between the local dataset and the official published reference.
2. The exact protocol-specific meaning of unusual ICMP and ESP values in the port columns.
3. The appropriate model-feature representation of `is_ftp_login` values 2 and 4.
4. The canonical spelling to use for the auxiliary attack-category representation.
5. The handling of exact duplicate groups during chronological dataset splitting.
6. The precise temporal boundaries for training, validation, and testing.

These questions will be addressed during implementation and evaluation, not through arbitrary modification of the original data.

## 13. Generated audit artifacts

Machine-readable reports are stored in:

`reports/data_quality/`

### Profiling reports

- `unsw_nb15_profile.json`
- `unsw_nb15_missing_values.csv`
- `unsw_nb15_numeric_validation.csv`
- `unsw_nb15_category_counts.csv`
- `unsw_nb15_label_attack_category.csv`
- `unsw_nb15_port_validation.csv`
- `unsw_nb15_port_special_value_contexts.csv`
- `unsw_nb15_ftp_login_anomalies.csv`

### Duplicate-analysis reports

- `unsw_nb15_duplicate_summary.json`
- `unsw_nb15_duplicate_groups.csv`
- `unsw_nb15_duplicate_occurrences.csv`

All reported findings were generated from the local original dataset.

## 14. Next engineering milestone

The next stage is reproducible full-dataset ingestion and Parquet storage.

That implementation will use the documented policies above and produce derived data without modifying the original CSV files.

Feature engineering, temporal splitting, model training, and subsequent production ML components will build on this validated data foundation.
