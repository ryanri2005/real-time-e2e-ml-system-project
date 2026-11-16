

\# UNSW-NB15 Dataset



\## Source



Official source:

https://research.unsw.edu.au/projects/unsw-nb15-dataset



Original research:

Moustafa and Slay (2015), UNSW-NB15:

A Comprehensive Data Set for Network Intrusion

Detection Systems.



\## Files



Four original network-event CSV files:



\- UNSW-NB15\_1.csv

\- UNSW-NB15\_2.csv

\- UNSW-NB15\_3.csv

\- UNSW-NB15\_4.csv



Feature metadata:



\- NUSW-NB15\_features.csv



The locally downloaded metadata file uses this

filename spelling.



\## Observed Dataset Statistics



File 1: 700,001 rows

File 2: 700,001 rows

File 3: 700,001 rows

File 4: 440,044 rows



Observed total: 2,540,047 rows.



The official UNSW page reports 2,540,044 records.

The three-record discrepancy is documented and

will be investigated during data-quality analysis.



No records have been removed to force the counts

to match.



\## Feature Schema



49 features and target fields.



Includes:

\- Source/destination network information

\- Protocol and connection state

\- Duration and traffic statistics

\- Packet and byte measurements

\- Timing information

\- Connection aggregation features

\- Attack category

\- Binary classification label



\## Prediction Target



Binary classification:



0 = Benign

1 = Malicious



The original attack category is retained for

additional evaluation.



\## Observed Class Distribution



Benign: 2,218,764

Malicious: 321,283



The dataset is imbalanced.



\## Category Consistency



The raw data contains both Backdoor and Backdoors.



These will be preserved in the original dataset

and normalized in derived analytical data.



\## Data Handling



Original data remains unchanged.



SHA-256 fingerprints are stored in:

unsw\_nb15\_manifest.json



Raw data is excluded from GitHub.



\## Licensing



Consult the official dataset page for usage terms.

The dataset is available for academic research;

commercial use requires agreement with the authors.



