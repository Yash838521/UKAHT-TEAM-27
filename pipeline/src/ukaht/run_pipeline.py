import argparse

from ukaht.config import load_config
from ukaht.enrich.florence_pipeline import run_florence
from ukaht.io_utils import load_inventory
from ukaht.tagging.clip_pipeline import run_clip


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the UKAHT image pipeline")
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=["clip", "florence"],
        default=["clip", "florence"],
        help="Pipeline parts to run",
    )
    args = parser.parse_args()

    config = load_config()
    records = load_inventory(config)
    print(f"Images in inventory: {len(records)}")

    if "clip" in args.steps:
        run_clip(config, records)
    if "florence" in args.steps:
        run_florence(config, records)

    print("Pipeline finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
