import json
import subprocess

import typer


def main(container_ip: str):
    # Run docker inspect to get container details
    result = subprocess.run(
        ["docker", "inspect", f"{container_ip}"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Failed to get container info:", result.stderr)
    else:
        # Parse the output as JSON
        container_info = json.loads(result.stdout)
        # Attempt to extract the IP address from the default network settings
        try:
            container_networks = container_info[0]["NetworkSettings"][
                "Networks"
            ]
            container_ip = next(iter(container_networks.values()))["IPAddress"]
            print(container_ip)
            # return container_ip
        except (IndexError, KeyError) as e:
            print("Error extracting IP address:", str(e))


if __name__ == "__main__":
    typer.run(main)
