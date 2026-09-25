import argparse
import os
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx


def measurement(high: bool = False) -> dict:
    return {
        "measurementId": str(uuid4()),
        "deviceId": "machine-42",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "powerKw": round(random.uniform(22, 28) if high else random.uniform(8, 19), 2),
        "temperatureC": round(random.uniform(78, 86) if high else random.uniform(45, 72), 2),
        "running": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="FactoryPulse device simulator")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--high", action="store_true")
    parser.add_argument("--interval", type=float, default=3)
    args = parser.parse_args()
    endpoint = os.getenv("FACTORYPULSE_API_URL", "http://localhost:8000") + "/api/v1/measurements"
    with httpx.Client(timeout=10) as client:
        while True:
            payload = measurement(args.high)
            response = client.post(endpoint, json=payload, headers={"X-Device-Key": "demo-device-key"})
            response.raise_for_status()
            print(response.json(), flush=True)
            if args.once: break
            time.sleep(args.interval)


if __name__ == "__main__":
    main()

