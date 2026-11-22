import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

API_SYNC_URL = "http://localhost:8000/stockout-alerts/sync"

STAGES = [
    (
        "BUILD LIVE FEATURES",
        [sys.executable, "-m", "ml.data.build_live_stockout_features"],
    ),
    (
        "GENERATE STOCKOUT PREDICTIONS",
        [sys.executable, "-m", "ml.models.generate_stockout_alerts"],
    ),
]


def run_stage(name, command):
    print(f"\n{'=' * 60}")
    print(f"STAGE: {name}")
    print("=" * 60)

    subprocess.run(
        command,
        cwd=ROOT,
        check=True,
    )

    print(f"\nSUCCESS: {name}")


def sync_alerts():
    print(f"\n{'=' * 60}")
    print("STAGE: SYNCHRONIZE ALERTS WITH POSTGRESQL")
    print("=" * 60)

    request = Request(
        API_SYNC_URL,
        data=b"",
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("processed_records", 0) <= 0:
        raise RuntimeError("No stockout alerts were synchronized.")

    print(json.dumps(result, indent=4))
    print("\nSUCCESS: DATABASE SYNCHRONIZATION")


def main():
    started_at = time.time()

    print("\nMEDISUPPLY AI - AUTOMATED STOCKOUT PIPELINE")
    print("=" * 60)

    try:
        for name, command in STAGES:
            run_stage(name, command)

        alerts_file = ROOT / "ml/data/stockout_alerts.csv"

        if not alerts_file.exists() or alerts_file.stat().st_size == 0:
            raise RuntimeError("Generated stockout alerts file is missing or empty.")

        sync_alerts()

        elapsed = time.time() - started_at

        print("\n" + "=" * 60)
        print("STOCKOUT PIPELINE COMPLETED SUCCESSFULLY")
        print(f"Execution time: {elapsed:.2f} seconds")
        print("=" * 60)

    except subprocess.CalledProcessError as exc:
        print(f"\nPIPELINE FAILED: Stage exited with code {exc.returncode}")
        sys.exit(1)

    except Exception as exc:
        print(f"\nPIPELINE FAILED: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
