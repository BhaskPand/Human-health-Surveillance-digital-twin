"""
╔══════════════════════════════════════════════════════════════╗
║   PHASE 1 — ML Model Training                                ║
║   Digital Twin for Hospital Patient Monitoring               ║
║                                                              ║
║   Run:    python train_model.py                              ║
║   Output: models/ folder with all model artifacts            ║
╚══════════════════════════════════════════════════════════════╝
"""

import pandas as pd
import numpy as np
import joblib
import os
import json
import warnings
warnings.filterwarnings("ignore")

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, roc_auc_score, f1_score
)

# ── 1. Load Dataset ───────────────────────────────────────────────────────────
print("=" * 65)
print("  DIGITAL TWIN — ML Model Training")
print("=" * 65)

CSV_PATH = "Synthetic_Health_Data.csv"
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(
        f"\n❌  Dataset not found at: {CSV_PATH}\n"
        "   → Place Synthetic_Health_Data.csv in the phase1_ml/ folder."
    )

df = pd.read_csv(CSV_PATH)
print(f"\n✅  Loaded: {df.shape[0]:,} rows × {df.shape[1]} columns")
print(f"    Columns: {list(df.columns)}")

# Check for nulls
nulls = df.isnull().sum().sum()
print(f"    Missing values: {nulls} {'✅' if nulls == 0 else '⚠️  (will drop)'}")
df = df.dropna()

print(f"\n    Label distribution:")
for label, count in df['Label'].value_counts().items():
    pct = count / len(df) * 100
    bar = "█" * int(pct / 2)
    print(f"      {str(label):12s}: {count:6,} ({pct:.1f}%)  {bar}")

# ── 2. Feature Engineering ────────────────────────────────────────────────────
BASE_FEATURES = ['Movement_Mag', 'HR', 'SpO2']
missing = [f for f in BASE_FEATURES if f not in df.columns]
if missing:
    raise ValueError(f"Missing columns: {missing}\nAvailable: {list(df.columns)}")

# Derived features — clinically meaningful
df['HR_SpO2_ratio']   = df['HR'] / (df['SpO2'] + 1e-6)   # cardiovascular stress index
df['movement_x_HR']   = df['Movement_Mag'] * df['HR']     # activity × cardiac load
df['SpO2_deficit']    = 100 - df['SpO2']                  # deviation from perfect oxygenation

FEATURES = BASE_FEATURES + ['HR_SpO2_ratio', 'movement_x_HR', 'SpO2_deficit']
X = df[FEATURES].values
y = df['Label'].values

# Encode labels
le = LabelEncoder()
y = le.fit_transform(y)
print(f"\n    Classes: {list(le.classes_)} → encoded as {list(range(len(le.classes_)))}")
print(f"    Feature set ({len(FEATURES)}): {FEATURES}")

# ── 3. Train / Test Split ─────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\n    Train: {len(X_train):,} | Test: {len(X_test):,}")

# ── 4. Scale Features ─────────────────────────────────────────────────────────
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train)
X_test_sc  = scaler.transform(X_test)

# ── 5. Random Forest (Primary Model) ─────────────────────────────────────────
print("\n" + "─" * 65)
print("  [1/2] Training Random Forest Classifier...")
print("─" * 65)

rf = RandomForestClassifier(
    n_estimators=300,
    max_depth=12,
    min_samples_split=5,
    min_samples_leaf=2,
    max_features='sqrt',
    class_weight='balanced',
    random_state=42,
    n_jobs=-1
)
rf.fit(X_train_sc, y_train)

y_pred  = rf.predict(X_test_sc)
y_proba = rf.predict_proba(X_test_sc)[:, 1]

acc = accuracy_score(y_test, y_pred)
auc = roc_auc_score(y_test, y_proba)
f1  = f1_score(y_test, y_pred, average='weighted')

print(f"\n  ✅  Accuracy  : {acc * 100:.2f}%")
print(f"  ✅  ROC-AUC   : {auc:.4f}")
print(f"  ✅  F1-Score  : {f1:.4f}")
print("\n  Classification Report:")
print(classification_report(y_test, y_pred, target_names=[str(c) for c in le.classes_]))
print("  Confusion Matrix:")
print(f"  {confusion_matrix(y_test, y_pred)}")

# 5-Fold Cross Validation
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(rf, scaler.transform(X), y, cv=cv, scoring='accuracy')
print(f"\n  5-Fold CV: {cv_scores.mean() * 100:.2f}% ± {cv_scores.std() * 100:.2f}%")

print("\n  Feature Importance:")
for feat, imp in sorted(zip(FEATURES, rf.feature_importances_), key=lambda x: -x[1]):
    bar = "█" * int(imp * 50)
    print(f"    {feat:22s}: {imp:.4f}  {bar}")

# ── 6. Gradient Boosting (Secondary / Ensemble) ───────────────────────────────
print("\n" + "─" * 65)
print("  [2/2] Training Gradient Boosting (ensemble backup)...")
print("─" * 65)

gb = GradientBoostingClassifier(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=5,
    subsample=0.8,
    random_state=42
)
gb.fit(X_train_sc, y_train)
gb_acc = accuracy_score(y_test, gb.predict(X_test_sc))
print(f"  Gradient Boosting Accuracy : {gb_acc * 100:.2f}%")

# Ensemble — average of both model probabilities
ens_proba = (rf.predict_proba(X_test_sc) + gb.predict_proba(X_test_sc)) / 2
ens_pred  = np.argmax(ens_proba, axis=1)
ens_acc   = accuracy_score(y_test, ens_pred)
print(f"  Ensemble Accuracy          : {ens_acc * 100:.2f}%")

# ── 7. Save All Artifacts ─────────────────────────────────────────────────────
os.makedirs("models", exist_ok=True)
joblib.dump(rf,     "models/rf_model.pkl")
joblib.dump(gb,     "models/gb_model.pkl")
joblib.dump(scaler, "models/scaler.pkl")
joblib.dump(le,     "models/label_encoder.pkl")

metadata = {
    "features":      FEATURES,
    "base_features": BASE_FEATURES,
    "classes":       [int(c) for c in le.classes_],
    "metrics": {
        "accuracy":  round(acc, 4),
        "roc_auc":   round(auc, 4),
        "f1_score":  round(f1, 4),
        "cv_mean":   round(cv_scores.mean(), 4),
        "cv_std":    round(cv_scores.std(), 4),
    },
    "thresholds": {
        "critical": 0.85,
        "warning":  0.60,
        "normal":   0.00
    }
}
with open("models/metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print("\n" + "=" * 65)
print("  ✅  All models saved to phase1_ml/models/")
print("      rf_model.pkl | gb_model.pkl | scaler.pkl")
print("      label_encoder.pkl | metadata.json")

# ── 8. Live Prediction Sanity Check ──────────────────────────────────────────
print("\n" + "─" * 65)
print("  Sanity Check — Live Predictions")
print("─" * 65)

def predict(hr, spo2, movement):
    features = np.array([[
        movement, hr, spo2,
        hr / (spo2 + 1e-6),
        movement * hr,
        100 - spo2
    ]])
    s     = scaler.transform(features)
    pred  = rf.predict(s)[0]
    prob  = rf.predict_proba(s)[0][1]
    label = le.inverse_transform([pred])[0]
    risk  = "🔴 CRITICAL" if prob > 0.85 else ("🟡 WARNING" if prob > 0.60 else "🟢 NORMAL ")
    return f"{risk} | {str(label):8s} | {prob:.3f} prob | HR={hr} SpO2={spo2}% Mov={movement}"

print(f"  Normal patient   → {predict(75,  98,  0.9)}")
print(f"  Warning patient  → {predict(105, 93,  2.1)}")
print(f"  Critical patient → {predict(140, 87,  4.2)}")
print(f"  Fall scenario    → {predict(120, 91,  8.5)}")

print("\n" + "=" * 65)
print("  🎉  Training complete!")
print("  ➡  Next: copy models/ into phase2_mqtt/ and phase3_backend/")
print("  ➡  Then run: python simulator.py  (in phase2_mqtt/)")
print("=" * 65)
