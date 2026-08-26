import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.jobs.generate_incident_lab import main

if __name__ == "__main__":
    main()
