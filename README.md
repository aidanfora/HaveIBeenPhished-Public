# Malicious URL Classifier

A machine learning pipeline for detecting malicious URLs using an ensemble architecture. 

## The Models

The classifier combines three distinct models to balance speed, feature engineering, and deep learning:

* **Logistic Regression:** A baseline model using Character and Word-based TF-IDF derived from our original training dataset.
* **XGBoost:** A gradient-boosted tree evaluating 100+ custom statistical, structural, and lexical features (e.g., entropy, brand typosquatting, abused TLDs).
* **Electra Transformer:** A lightweight LLM fine-tuned for sequence classification to catch complex semantic patterns in the URL.

A URL is flagged as malicious if the combined ensemble score meets or exceeds a `0.50` threshold.

## Project Structure

* `features.py`: Contains the URL parser and feature extraction logic used by the XGBoost model.
* `models.py`: Handles loading the pre-trained weights, executing inference across all three models, and calculating the final ensemble score.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```
2. Ensure your `models/` directory contains the pre-trained weights (`logreg.joblib`, `xgboost.json`, and the `electra` transformer files).

## Usage

You can evaluate any URL by passing it to the main ensemble function.

```python
from models import evaluate_url

target_url = "[http://secure-login-update-auth.com](http://secure-login-update-auth.com)"
is_malicious, score = evaluate_url(target_url)

if is_malicious:
    print(f"[!] MALICIOUS URL DETECTED (Score: {score:.3f})")
else:
    print(f"[+] URL is benign (Score: {score:.3f})")
```