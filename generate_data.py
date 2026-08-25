import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.engine.seed_data import seed_database

def main():
    parser = argparse.ArgumentParser(description="MoneyOps AI — Financial Data & Incident Generator")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible generation")
    parser.add_argument("--transactions", type=int, default=2500, help="Number of baseline transactions to generate")
    parser.add_argument("--merchants", type=int, default=25, help="Number of merchants to generate")
    parser.add_argument("--clean", action="store_true", help="Drop and recreate clean database tables before generation")

    args = parser.parse_args()

    print("=" * 60)
    print(" MONEYOPS AI — SYNTHETIC FINANCIAL EVENT & INCIDENT GENERATOR")
    print("=" * 60)
    print(f" Config: Seed={args.seed} | Transactions={args.transactions} | Merchants={args.merchants}")
    print(" Generating realistic financial lifecycles and injecting 4 golden demo incidents...")
    
    summary = seed_database(seed=args.seed, n_transactions=args.transactions, n_merchants=args.merchants)
    
    print("\nGeneration Complete:")
    for k, v in summary.items():
        print(f"  - {k}: {v}")
    print("=" * 60)

if __name__ == "__main__":
    main()
