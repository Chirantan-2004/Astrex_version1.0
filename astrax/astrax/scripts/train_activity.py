"""Train a lightweight activity classifier when real numeric features are available.

Expected CSV columns: label plus numeric feature columns. The demo app does not require
this model; this is the bridge to experiment-specific trained HAR.
"""
import argparse
from pathlib import Path
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

p=argparse.ArgumentParser(); p.add_argument('--input',default='data/dataset/features.csv'); p.add_argument('--output',default='models/activity_model.pkl'); a=p.parse_args()
df=pd.read_csv(a.input)
if 'label' not in df.columns: raise SystemExit('CSV needs a label column.')
X=df.drop(columns=[c for c in ['label','timestamp'] if c in df.columns])
if X.shape[1] == 0: raise SystemExit('No numeric feature columns. Add pose/object features before training.')
y=df['label']
if len(df)<10: raise SystemExit('Collect at least 10 labeled rows; substantially more is recommended for a real model.')
X=X.apply(pd.to_numeric,errors='coerce').fillna(0)
model=RandomForestClassifier(n_estimators=150,random_state=42,class_weight='balanced')
model.fit(X,y)
Path(a.output).parent.mkdir(parents=True,exist_ok=True); joblib.dump(model,a.output)
print(f'Saved {a.output}')
