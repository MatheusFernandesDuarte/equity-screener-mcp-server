# run.py


import sys

from src.app.main import run


def main() -> None:
    """Entry point for the Yahoo Finance Crawler CLI."""
    if len(sys.argv) < 2:
        print("❌ Error: Region argument is missing.")
        print("Usage: python run.py <region_name>")
        sys.exit(1)

    region: str = " ".join(sys.argv[1:])
    run(region=region)


if __name__ == "__main__":
    main()
