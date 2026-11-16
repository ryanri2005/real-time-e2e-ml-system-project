\# UNSW-NB15 Bronze Ingestion



\## 1. Purpose



The Bronze layer is the first persisted data layer in the A1 cybersecurity

machine-learning pipeline.



Its purpose is to convert the four original, headerless UNSW-NB15 CSV files

into efficient, queryable Parquet files while preserving the parsed source

feature values.



Bronze is intentionally a raw-preserving layer. It does not perform

feature engineering, imputation, categorical encoding, numeric conversion,

label normalization, or duplicate removal. Those decisions belong in

subsequent processing stages.



The implementation is designed to be:



\- Reproducible through source-file checksums and an ingestion manifest.

\- Memory-efficient through chunk-based CSV processing.

\- Auditable through per-record source provenance.

\- Safe against incomplete publication and accidental overwrites.

\- Independently verifiable against the original CSV files.



\## 2. Input data



The source dataset is stored locally under:



`data/raw/UNSW-NB15/`



The four data files are:



| Source file | Records |

|---|---:|

| `UNSW-NB15\_1.csv` | 700,001 |

| `UNSW-NB15\_2.csv` | 700,001 |

| `UNSW-NB15\_3.csv` | 700,001 |

| `UNSW-NB15\_4.csv` | 440,044 |

| \*\*Total\*\* | \*\*2,540,047\*\* |



The feature metadata file is:



`NUSW-NB15\_features.csv`



The source CSVs do not contain a header row. Feature names and

feature definitions are loaded through the project's existing

feature-metadata loader.



Before ingestion, the implementation verifies all five original files

against:



`docs/datasets/unsw\_nb15\_manifest.json`



The verification checks each file's expected byte size and SHA-256

fingerprint. This includes the four data CSVs and the feature metadata file.



The local source files contain 2,540,047 records. This differs from the

2,540,044 records reported in the dataset's published overview. The

pipeline preserves the complete local source files rather than deleting

records to force agreement with the published count. This discrepancy

remains documented for further investigation.



\## 3. Bronze output



The generated dataset is stored under:



`data/processed/bronze/`



The directory contains:



| Output file | Source |

|---|---|

| `UNSW-NB15\_1.parquet` | `UNSW-NB15\_1.csv` |

| `UNSW-NB15\_2.parquet` | `UNSW-NB15\_2.csv` |

| `UNSW-NB15\_3.parquet` | `UNSW-NB15\_3.csv` |

| `UNSW-NB15\_4.parquet` | `UNSW-NB15\_4.csv` |

| `ingestion\_manifest.json` | Ingestion metadata and verification information |



Each source CSV is converted into one corresponding Parquet file.



The output uses Zstandard (`zstd`) compression, dictionary encoding,

and Parquet statistics.



The completed local output was approximately 155.60 MiB across the

four Parquet files.



\## 4. Schema and preservation rules



\### Original feature columns



All 49 source features are stored as Parquet strings.



This is deliberate. Bronze does not assume that every value can be

safely interpreted as a number or that every unusual value is invalid.



For example, values such as:



\- Empty strings

\- Whitespace-only strings

\- Hexadecimal-looking strings

\- Dash sentinels

\- Numeric-looking strings

\- Categorical values



remain represented as their parsed CSV field values.



The CSV reader handles CSV quoting and delimiters. Consequently, Bronze

preserves the decoded field contents, not the original byte-for-byte CSV

formatting, quoting, or line endings.



No source values are globally stripped, numerically coerced, or

reclassified during ingestion.



\### Provenance columns



Two additional columns are added to every Parquet file:



| Column | Type | Meaning |

|---|---|---|

| `\_source\_file` | string | Original CSV filename |

| `\_source\_record\_number` | int64 | 1-based record number within that CSV |



The record number starts at 1 independently for each source CSV.



These columns make it possible to trace any Bronze record back to its

original file and record position.



\### Total Bronze schema



Each Parquet file contains 51 columns:



\- 49 original feature columns, stored as strings.

\- 2 provenance columns.



\## 5. Streaming and row-group design



Ingestion processes the CSV files in chunks instead of loading the

entire dataset into memory.



The default chunk size is 25,000 records.



Each chunk is written to Parquet as a row group. This limits memory

usage while producing Parquet files that support efficient columnar

reading.



The completed ingestion produced:



| Source file | Records | Row groups |

|---|---:|---:|

| `UNSW-NB15\_1.csv` | 700,001 | 29 |

| `UNSW-NB15\_2.csv` | 700,001 | 29 |

| `UNSW-NB15\_3.csv` | 700,001 | 29 |

| `UNSW-NB15\_4.csv` | 440,044 | 18 |

| \*\*Total\*\* | \*\*2,540,047\*\* | \*\*105\*\* |



The final row group of each file contains the remaining records after

the full 25,000-record chunks have been written.



\## 6. Source integrity and safe publication



The ingestion process applies several safeguards.



\### Before ingestion



1\. Loads the existing source manifest.

2\. Confirms that all five expected source files exist.

3\. Verifies their file sizes.

4\. Recalculates and checks their SHA-256 fingerprints.

5\. Loads the feature definitions used to construct the Parquet schema.



\### During ingestion



1\. Reads each source CSV incrementally.

2\. Checks each record's field count against the expected 49 features.

3\. Rejects blank records and malformed CSV input.

4\. Writes each completed chunk as a Parquet row group.

5\. Calculates the source file's SHA-256 again after conversion.

6\. Compares that fingerprint with the pre-ingestion fingerprint.



If the input file changes during processing, the run fails.



\### Publication



The four Parquet files and ingestion manifest are first written to a

temporary staging directory under `data/processed/`.



The completed staging directory is renamed to `data/processed/bronze`

only after every source file has been processed successfully and the

manifest has been written.



The implementation refuses to overwrite an existing Bronze output

directory. A failed run cleans up its staging directory rather than

publishing an incomplete Bronze dataset.



\## 7. Ingestion manifest



The generated file:



`data/processed/bronze/ingestion\_manifest.json`



records information about the completed ingestion.



It includes:



\- Dataset name and layer.

\- UTC generation timestamp.

\- Chunk size and compression codec.

\- Source manifest location and generation timestamp.

\- Source filenames, file sizes, and SHA-256 fingerprints.

\- The 49-feature schema, including source feature types and Bronze types.

\- The two provenance-column definitions.

\- Total record count.

\- Per-file source and Parquet filenames.

\- Per-file record counts and row-group counts.

\- Per-file output sizes.

\- Per-file source and output SHA-256 fingerprints.



The manifest is intended to make the ingestion reproducible and

auditable without storing the original raw data in Git.



\## 8. Independent verification



The implementation includes:



`scripts/verify\_unsw\_nb15\_bronze.py`



This verifier independently compares the original CSV files with

their corresponding Parquet outputs.



It does not rely solely on ingestion summary counts. It reads the

original CSV files and Parquet files in batches and compares every

feature value for every record.



It also verifies:



\- Source-file checksums against the source manifest.

\- Parquet-file checksums against the ingestion manifest.

\- File sizes and record counts.

\- All 49 feature names and their string types.

\- The provenance-column names and types.

\- Source filenames for every record.

\- 1-based source record numbers for every record.

\- Parquet compression codec.

\- Row-group counts.

\- The total record count across all four files.

\- That the original CSV files contain no additional records after

&#x20; the Parquet data ends.



The default verification batch size is 10,000 records. Verification

batch size is independent of ingestion chunk size.



\### Completed verification results



The independent verifier completed successfully.



| Verification | Result |

|---|---:|

| Source files checked | 4 |

| Records compared | 2,540,047 |

| Original features compared | 49 |

| Row groups checked | 105 |

| Provenance checks | Passed |

| Compression checks | Passed |

| Checksums | Passed |

| Schema checks | Passed |



All original feature values matched their corresponding Parquet values.



The original CSV files were not modified.



\## 9. Automated tests



The Bronze implementation is covered by:



`tests/test\_bronze\_ingestion.py`



The tests use small synthetic datasets and temporary directories. They

do not alter the actual UNSW-NB15 raw dataset.



The tests cover:



\- Preservation of empty strings and whitespace.

\- Preservation of hexadecimal-looking and categorical values.

\- Correct handling of CSV commas and quotes.

\- String feature types and int64 record-number type.

\- Source filename and record-number provenance.

\- Chunking and Parquet row-group creation.

\- Rejection of incorrect field counts.

\- Rejection of blank records.

\- Rejection of empty CSV files.

\- Successful end-to-end ingestion of synthetic source files.

\- Source-manifest integrity checks.

\- Detection of a changed source file when its size remains unchanged.

\- Refusal to overwrite an existing Bronze directory.

\- Cleanup of temporary output files after failures.



The complete project test suite and repository-wide Ruff checks

passed after implementation.



\## 10. Reproducing the ingestion



From the repository root, run:



```powershell

uv run python .\\scripts\\ingest\_unsw\_nb15\_bronze.py
