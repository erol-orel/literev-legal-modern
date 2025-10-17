import sys

from datetime import datetime

import requests

ES_URL = "http://staging.literev.com:9200"
SNAPSHOT_REPO = "literev_backup"
DISCORD_WEBHOOK_URL = ""

REQUIRED_INDICES = [
    "civil_court",
    "penal_court",
    "administrative_court",
    "chambre_penale",
    "chambre_civile",
    "chambre_administrative",
]


def check_index_exists(index):
    url = f"{ES_URL}/{index}"
    response = requests.head(url)
    return response.status_code == 200


def get_latest_snapshot():
    url = f"{ES_URL}/_snapshot/{SNAPSHOT_REPO}/_all"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to get snapshots: {response.text}")

    snapshots = response.json().get("snapshots", [])
    if not snapshots:
        raise Exception("No snapshots found!")

    latest = sorted(
        snapshots, key=lambda x: x["start_time_in_millis"], reverse=True
    )[0]
    return latest["snapshot"]


def restore_indices(indices, snapshot_name):
    url = f"{ES_URL}/_snapshot/{SNAPSHOT_REPO}/{snapshot_name}/_restore"
    payload = {
        "indices": ",".join(indices),
        "ignore_unavailable": True,
        "include_global_state": True,
    }
    response = requests.post(url, json=payload)
    if response.status_code not in [200, 202]:
        raise Exception(f"Restore failed: {response.text}")
    return response.json()


def notify_discord(message):
    if not DISCORD_WEBHOOK_URL:
        return
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)


if __name__ == "__main__":
    try:
        print(f"[{datetime.now()}] Checking indices...")
        missing = []

        for idx in REQUIRED_INDICES:
            if not check_index_exists(idx):
                print(f"Missing index: {idx}")
                missing.append(idx)
            else:
                print(f"Index exists: {idx}")

        if not missing:
            print("All indices are present. No restore needed.")
            sys.exit(0)

        print(f"Missing indices detected: {missing}")
        notify_discord(
            f"*Elasticsearch Alert*: Missing indices detected: {', '.join(missing)}. Starting restore..."
        )

        latest_snapshot = get_latest_snapshot()
        print(f"Latest snapshot: {latest_snapshot}")

        result = restore_indices(missing, latest_snapshot)
        print(f"Restore triggered: {result}")

        notify_discord(
            f"*Restore completed* for indices: {', '.join(missing)} from snapshot `{latest_snapshot}`"
        )

    except Exception as e:
        error_message = f"*Restore script error:* {e}"
        print(error_message)
        notify_discord(error_message)
        sys.exit(1)
