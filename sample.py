import joblib
import xgboost
import torch
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from features import extract_features 

# load the models (LR, XGBoost, Electra)
logreg = joblib.load('models/logreg.joblib')
xgb = xgboost.Booster(model_file='models/xgboost.json')
tokenizer = AutoTokenizer.from_pretrained('models/electra')
electra = AutoModelForSequenceClassification.from_pretrained('models/electra')

# extracts malicious probability scores from all three models
def get_predictions(url: str) -> tuple[float, float, float]:
    # LR
    p_lr = logreg.predict_proba([url])[0][1]
    
    # XGBoost
    features = extract_features(url)
    p_xgb = xgb.predict(xgboost.DMatrix(pd.DataFrame([features])))[0] if features else 0.0
    
    # Electra
    inputs = tokenizer(url, return_tensors="pt", truncation=True, max_length=256)
    with torch.no_grad():
        logits = electra(**inputs).logits
        p_electra = torch.nn.functional.softmax(logits, dim=-1)[0][1].item()
        
    return p_lr, p_xgb, p_electra

def evaluate_url(url: str):
    # run inference
    p_lr, p_xgb, p_electra = get_predictions(url)
    
    # weighted ensemble
    ensemble_score = (0.25 * p_lr) + (0.30 * p_xgb) + (0.45 * p_electra)
    
    is_malicious = ensemble_score >= 0.50
    return is_malicious, ensemble_score

target_url = "http://secure-login-update-auth.com"
is_mal, score = evaluate_url(target_url)

print(f"Target: {target_url}")
print(f"Verdict: {'MALICIOUS' if is_mal else 'BENIGN'} (Ensemble Score: {score:.3f})")