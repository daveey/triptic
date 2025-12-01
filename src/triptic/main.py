"""Main entry point."""

import sys


def main() -> int:
    """Main function - delegates to CLI."""
    from triptic.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
