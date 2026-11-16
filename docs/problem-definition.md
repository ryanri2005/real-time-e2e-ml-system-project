# A1 - Problem Definition

## 1. Project Objective

Build an end-to-end production ML system that processes network/security events, predicts whether they are malicious, and generates risk scores to prioritize potentially malicious events for investigation.

The focus is ML engineering, production ML systems, reproducibility, scalability, reliability, and model lifecycle management.

## 2. Prediction Problem

Type: Supervised binary classification.

Prediction unit: An individual network/security event or flow. The exact record granularity will be confirmed after dataset inspection.

Target:

- 0: Benign
- 1: Malicious

The original attack categories will also be retained where available for more detailed model evaluation.

## 3. Model Inputs

The model will use relevant numerical and categorical features available at prediction time.

The final feature list will be established after dataset exploration and feature engineering.

Labels, future information, and fields that would introduce data leakage must not be used as prediction inputs.

## 4. Model Outputs

The system should produce:

- Predicted class.
- Probability of malicious activity.
- Risk score.
- Model version.
- Feature schema/version information.

The initial risk score can be expressed on a 0-100 scale based on the model's malicious probability.

The operating classification threshold will be selected through model evaluation and calibration.

## 5. Evaluation Objectives

Model quality:

- Precision.
- Recall.
- F1.
- PR-AUC.
- ROC-AUC.
- False-positive rate.
- Calibration.
- Performance across attack categories.

Production performance:

- p50/p95/p99 inference latency.
- Throughput.
- CPU and memory utilization.
- Model size and computational cost.

Numeric acceptance thresholds will be established using baseline measurements and operational tradeoffs rather than invented in advance.

## 6. Data Correctness

Use time-aware training, validation, and testing.

Prevent future information from entering historical training features.

Ensure feature transformations remain consistent between training and inference.

## 7. Production Objectives

The system should eventually support:

- Online inference.
- Batch inference.
- Event-stream processing.
- Model version management.
- Experiment tracking.
- Model registry.
- Production monitoring.
- Data/model drift detection.
- Automated retraining.
- Candidate validation.
- Controlled deployment and rollback.

## 8. Scope Boundaries

This project develops an ML engineering workload within cybersecurity.

It is not intended to recreate an entire SIEM, SOC, or enterprise cybersecurity platform.

The main objective is to demonstrate the ability to develop, evaluate, deploy, monitor, optimize, and continuously improve production ML systems.
