"""Collect simple pose/object feature rows for a future activity model.

This script is intentionally lightweight. It records labels and timestamps; integrate
MediaPipe/YOLO feature extraction on the target machine when those packages are installed.
"""
import csv
import argparse
from datetime import datetime, timezone
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--label', required=True, choices=['IDLE','OPEN','PICK','INSERT','ROTATE','CLOSE'])
parser.add_argument('--output', default='data/dataset/features.csv')
args=parser.parse_args()

path=Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
exists=path.exists()
with path.open('a',newline='',encoding='utf-8') as f:
    w=csv.writer(f)
    if not exists: w.writerow(['timestamp','label'])
    w.writerow([datetime.now(timezone.utc).isoformat(),args.label])
print(f'Added labeled sample: {args.label} -> {path}')
