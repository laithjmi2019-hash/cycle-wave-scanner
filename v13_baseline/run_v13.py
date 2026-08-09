"""
V13 BASELINE — Preserved checkpoint. Do not modify.
Run: python v13_baseline/run_v13.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telegram_bot import run_scan
if __name__ == "__main__":
    run_scan()
