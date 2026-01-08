# run.py


import sys

from src.app.main import run


def main() -> None:
    """
    Entry point for the Yahoo Finance Crawler CLI.

    Validates input arguments and triggers the main orchestration logic.
    """
    if len(sys.argv) < 2:
        print("\n❌ Error: Region argument is missing.")
        print("💡 Usage: uv run run.py <region_name>")
        print("📋 Example: uv run run.py Argentina\n")
        sys.exit(1)

    region: str = " ".join(sys.argv[1:]).strip()

    if not region:
        print("❌ Error: Region name cannot be empty.")
        sys.exit(1)

    try:
        run(region=region)
    except KeyboardInterrupt:
        print("\n\n🛑 Operation cancelled by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
