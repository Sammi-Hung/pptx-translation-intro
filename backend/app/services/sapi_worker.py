import argparse
from pathlib import Path
import sys

from app.core.errors import UserFacingError
from app.services.tts import synthesize_with_sapi_in_process


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True)
    parser.add_argument("--text-file", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        text = Path(args.text_file).read_text(encoding="utf-8")
        synthesize_with_sapi_in_process(text, args.language, Path(args.output))
    except UserFacingError as exc:
        print(exc.message, file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Windows SAPI worker failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
