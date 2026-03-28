from __future__ import annotations

import logging
import sys

from .config import build_config, build_parser
from .extractor import extract_positions
from .output import write_records


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = build_config(args)
    except Exception as exc:
        parser.error(str(exc))
        return 2

    configure_logging(config.log_level)
    records = extract_positions(config)
    write_records(records, config.output_path, config.output_format, config.mode)
    logging.getLogger(__name__).info("Wrote %s record(s) to %s", len(records), config.output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
