
# UNSW-NB15 Dataset

## 1. Dataset source

**Official dataset:** UNSW-NB15

**Official source:**

https://research.unsw.edu.au/projects/unsw-nb15-dataset

**Original research:**

Moustafa and Slay (2015), *UNSW-NB15: A Comprehensive Data Set for Network Intrusion Detection Systems.*

The dataset contains network traffic records intended for network intrusion detection research.

## 2. Local dataset files

The local dataset contains four original CSV files:

| File | Observed records |
|---|---:|
| `UNSW-NB15_1.csv` | 700,001 |
| `UNSW-NB15_2.csv` | 700,001 |
| `UNSW-NB15_3.csv` | 700,001 |
| `UNSW-NB15_4.csv` | 440,044 |
| **Total** | **2,540,047** |

The four CSV files do not contain a header row. Feature names are loaded from the accompanying metadata file.

**Feature metadata file:**

`NUSW-NB15_features.csv`

The local metadata filename uses this spelling, including the initial `N`.

## 3. Record-count discrepancy

The official UNSW dataset page reports 2,540,044 records.

Inspection of the four locally downloaded files found 2,540,047 records.

The difference is three records.

The local record count was independently verified using:

- Chunked pandas dataset inspection.
- Full-dataset CSV structural validation.
- Full-dataset data-quality profiling.
- Full-dataset duplicate analysis.

All four files produced consistent record counts during these verification runs.

The difference from the official published reference has not been conclusively explained.

**Data-handling decision:** All 2,540,047 locally observed records are preserved. No records have been removed to force agreement with the published reference.

## 4. Feature schema

The dataset contains 49 features.

| Metadata type | Number of features |
|---|---:|
| Nominal | 6 |
| Integer | 28 |
| Float | 10 |
| Timestamp | 2 |
| Binary | 3 |
| **Total** | **49** |

Feature names are loaded from the original metadata file.

The internal schema removes accidental whitespace and converts feature names to lowercase.

For example:

`ct_src_ ltm` becomes `ct_src_ltm`.

This normalization applies to internal column names, not the original CSV records.

## 5. Prediction targets

### Binary classification target

The primary prediction target is `label`:

- `0` = Normal or benign traffic.
- `1` = Attack or malicious traffic.

### Attack-category field

The `attack_cat` field provides additional information about malicious traffic.

The nine intended attack categories are:

- Analysis
- Backdoors
- DoS
- Exploits
- Fuzzers
- Generic
- Reconnaissance
- Shellcode
- Worms

The local raw data contains both `Backdoor` and `Backdoors`. These values are preserved in the original data and documented for downstream category normalization.

Benign records have no attack category.

## 6. Dataset files and project documentation

The original dataset files are stored locally under:

`data/raw/UNSW-NB15/`

Raw data is excluded from GitHub.

The following files document the dataset and its processing:

- [Dataset manifest](unsw_nb15_manifest.json)
- [EDA findings](eda-findings.md)
- [Data-quality report and preprocessing specification](data-quality-and-preprocessing.md)

Generated data-quality reports are stored under:

`reports/data_quality/`

## 7. Data integrity and handling

The original CSV files are treated as immutable source data.

A SHA-256 manifest records the file sizes and fingerprints of the four CSV files and the feature metadata file.

Structural validation established that:

- All four CSV files can be parsed.
- Every nonblank record contains exactly 49 fields.
- No blank records were encountered.
- No malformed records were encountered.

Full-dataset profiling and duplicate analysis are documented separately.

No automatic deletion or modification of raw observations is performed.

## 8. Licensing

Consult the official UNSW dataset page for the applicable usage terms.

The dataset is provided for academic research; commercial usage requires agreement with the authors.
