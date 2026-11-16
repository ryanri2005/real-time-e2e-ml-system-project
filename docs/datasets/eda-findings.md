# UNSW-NB15 Exploratory Data Analysis

## 1. Dataset sample

- Sample records: 12,700
- Feature/label columns: 49
- Sampling method: deterministic 0.5% sampling 
  from each 100,000-record chunk.

This is an exploratory sample, not the full 
training or testing dataset.

## 2. Binary label distribution

label
0    11069
1     1631

## 3. Attack category distribution

attack_cat
<MISSING>         11069
Generic            1090
Exploits            226
Fuzzers             130
DoS                  90
Reconnaissance       66
Analysis             14
Shellcode             8
Backdoors             4
Backdoor              3

## 4. Missing values

attack_cat          11069
is_ftp_login         7161
ct_flw_http_mthd     6729
sport                   0
proto                   0
state                   0
dstip                   0
dsport                  0
dbytes                  0
sttl                    0
dttl                    0
sloss                   0
dloss                   0
service                 0
dur                     0
sbytes                  0
srcip                   0
spkts                   0
dload                   0
sload                   0
dpkts                   0
dtcpb                   0
swin                    0
dwin                    0
stcpb                   0
res_bdy_len             0
sjit                    0
djit                    0
stime                   0
ltime                   0
smeansz                 0
dmeansz                 0
trans_depth             0
tcprtt                  0
dintpkt                 0
sintpkt                 0
synack                  0
ct_state_ttl            0
is_sm_ips_ports         0
ct_ftp_cmd              0
ackdat                  0
ct_srv_src              0
ct_srv_dst              0
ct_src_ltm              0
ct_dst_ltm              0
ct_src_dport_ltm        0
ct_dst_sport_ltm        0
ct_dst_src_ltm          0
label                   0

## 5. Duplicate observations

Exact duplicate rows in EDA sample: 97

This count applies to the sample only, not the 
complete original dataset.

## 6. Numerical feature summary

```text
                    count          mean           std           min           25%           50%           75%           max
dur               12700.0  5.973695e-01  3.390244e+00  0.000000e+00  1.037000e-03  1.511600e-02  1.926017e-01  5.999999e+01
sbytes            12700.0  4.022029e+03  1.617223e+04  2.800000e+01  2.000000e+02  1.470000e+03  3.302000e+03  9.521810e+05
dbytes            12700.0  3.343426e+04  1.490764e+05  0.000000e+00  1.640000e+02  1.728000e+03  1.495200e+04  2.026298e+06
sttl              12700.0  6.317339e+01  7.510178e+01  0.000000e+00  3.100000e+01  3.100000e+01  3.100000e+01  2.540000e+02
dttl              12700.0  3.111205e+01  4.366819e+01  0.000000e+00  2.900000e+01  2.900000e+01  2.900000e+01  2.540000e+02
sloss             12700.0  4.970945e+00  1.000563e+01  0.000000e+00  0.000000e+00  3.000000e+00  7.000000e+00  3.940000e+02
dloss             12700.0  1.524008e+01  5.218240e+01  0.000000e+00  0.000000e+00  4.000000e+00  1.400000e+01  7.420000e+02
sload             12700.0  3.771386e+07  1.244364e+08  0.000000e+00  1.621142e+05  5.910931e+05  2.021841e+06  3.392000e+09
dload             12700.0  2.511946e+06  4.291469e+06  0.000000e+00  1.095623e+04  5.932497e+05  3.087125e+06  2.171544e+07
spkts             12700.0  3.188984e+01  6.144937e+01  1.000000e+00  2.000000e+00  1.200000e+01  4.400000e+01  7.900000e+02
dpkts             12700.0  4.028701e+01  1.121175e+02  0.000000e+00  2.000000e+00  1.200000e+01  4.200000e+01  1.488000e+03
swin              12700.0  1.498677e+02  1.255276e+02  0.000000e+00  0.000000e+00  2.550000e+02  2.550000e+02  2.550000e+02
dwin              12700.0  1.494260e+02  1.256055e+02  0.000000e+00  0.000000e+00  2.550000e+02  2.550000e+02  2.550000e+02
stcpb             12700.0  1.262393e+09  1.422810e+09  0.000000e+00  0.000000e+00  6.392257e+08  2.488332e+09  4.294035e+09
dtcpb             12700.0  1.265832e+09  1.427176e+09  0.000000e+00  0.000000e+00  6.438148e+08  2.478080e+09  4.294753e+09
smeansz           12700.0  1.256213e+02  1.539397e+02  2.800000e+01  6.100000e+01  7.300000e+01  1.320000e+02  1.497000e+03
dmeansz           12700.0  2.754594e+02  3.314243e+02  0.000000e+00  6.900000e+01  8.900000e+01  5.650000e+02  1.463000e+03
trans_depth       12700.0  8.362205e-02  2.827415e-01  0.000000e+00  0.000000e+00  0.000000e+00  0.000000e+00  2.000000e+00
res_bdy_len       12700.0  4.147337e+03  4.535810e+04  0.000000e+00  0.000000e+00  0.000000e+00  0.000000e+00  9.829590e+05
sjit              12700.0  1.593844e+03  1.818915e+04  0.000000e+00  0.000000e+00  1.911083e+01  3.614183e+02  1.151450e+06
djit              12700.0  7.120428e+02  2.317389e+03  0.000000e+00  0.000000e+00  2.623132e+00  6.292704e+01  4.885760e+04
stime             12700.0  1.423260e+09  1.134557e+06  1.421927e+09  1.421952e+09  1.424227e+09  1.424245e+09  1.424262e+09
ltime             12700.0  1.423260e+09  1.134556e+06  1.421927e+09  1.421952e+09  1.424227e+09  1.424245e+09  1.424262e+09
sintpkt           12700.0  2.033908e+02  2.884510e+03  0.000000e+00  9.000000e-03  4.673330e-01  6.795022e+00  6.000111e+04
dintpkt           12700.0  6.436048e+01  1.178434e+03  0.000000e+00  6.000000e-03  4.092935e-01  5.928035e+00  4.885760e+04
tcprtt            12700.0  6.419004e-03  5.578899e-02  0.000000e+00  0.000000e+00  6.130000e-04  7.020000e-04  4.601523e+00
synack            12700.0  3.491900e-03  3.938350e-02  0.000000e+00  0.000000e+00  4.830000e-04  5.550000e-04  3.882003e+00
ackdat            12700.0  2.927104e-03  2.282219e-02  0.000000e+00  0.000000e+00  1.220000e-04  1.400000e-04  1.573404e+00
is_sm_ips_ports   12700.0  1.968504e-03  4.432588e-02  0.000000e+00  0.000000e+00  0.000000e+00  0.000000e+00  1.000000e+00
ct_state_ttl      12700.0  2.671654e-01  6.981976e-01  0.000000e+00  0.000000e+00  0.000000e+00  0.000000e+00  6.000000e+00
ct_flw_http_mthd   5971.0  2.252554e-01  6.692619e-01  0.000000e+00  0.000000e+00  0.000000e+00  0.000000e+00  1.000000e+01
is_ftp_login       5539.0  3.448276e-02  1.883257e-01  0.000000e+00  0.000000e+00  0.000000e+00  0.000000e+00  4.000000e+00
ct_srv_src        12700.0  9.153780e+00  1.078705e+01  1.000000e+00  2.000000e+00  5.000000e+00  1.000000e+01  6.600000e+01
ct_srv_dst        12700.0  8.903150e+00  1.076763e+01  1.000000e+00  2.000000e+00  5.000000e+00  1.000000e+01  6.600000e+01
ct_dst_ltm        12700.0  6.435276e+00  8.255706e+00  1.000000e+00  2.000000e+00  3.000000e+00  6.000000e+00  6.000000e+01
ct_src_ltm        12700.0  6.908976e+00  8.301293e+00  1.000000e+00  2.000000e+00  4.000000e+00  7.000000e+00  6.000000e+01
ct_src_dport_ltm  12700.0  4.639291e+00  8.559554e+00  1.000000e+00  1.000000e+00  1.000000e+00  2.000000e+00  6.000000e+01
ct_dst_sport_ltm  12700.0  3.591024e+00  6.231635e+00  1.000000e+00  1.000000e+00  1.000000e+00  1.000000e+00  6.000000e+01
ct_dst_src_ltm    12700.0  6.784409e+00  1.119092e+01  1.000000e+00  1.000000e+00  2.000000e+00  4.000000e+00  6.600000e+01
```

## 7. Timestamp analysis

### stime

- Earliest: 2015-01-22 11:50:23+00:00
- Latest: 2015-02-18 12:20:40+00:00
- Invalid/unconvertible: 0

### ltime

- Earliest: 2015-01-22 11:50:23+00:00
- Latest: 2015-02-18 12:20:40+00:00
- Invalid/unconvertible: 0

## 8. High-cardinality features

```text
ltime      11600
stime      11598
sport       9698
sload       9002
dload       8758
dur         8307
sintpkt     8148
djit        8146
dintpkt     7993
sjit        7835
stcpb       7440
dtcpb       7440
dsport      3960
tcprtt      1202
dbytes      1201
synack      1052
sbytes      1023
ackdat       803
dmeansz      631
smeansz      324
```

## 9. Initial observations

- The dataset contains benign and malicious events.
- The binary labels are imbalanced.
- Attack categories are retained separately.
- Missing attack categories must be interpreted 
  carefully because benign records may not have 
  an attack category.
- Backdoor and Backdoors are spelling variants 
  that require documented normalization.
- Source and destination identifiers require 
  further investigation before feature selection.

## 10. Data-quality limitations and next steps

- The observed complete dataset contained 
  2,540,047 records.
- The official UNSW page reports 2,540,044 records.
- This discrepancy requires further investigation.
- Full-dataset duplicate and data-quality analysis 
  is still required.
- No raw data has been modified.

## 11. Evaluation considerations

- Avoid random splitting where it creates temporal 
  or related-record leakage.
- Examine feature and label distributions over time.
- Preserve an untouched chronological test period.
- Evaluate precision, recall, PR-AUC, FPR and 
  calibration rather than accuracy alone.
