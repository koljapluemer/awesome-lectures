"""Validate all data/*.json files against schema.json."""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("jsonschema not installed — run: uv add jsonschema", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schema.json"
DATA_DIR = ROOT / "data"


def main() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft7Validator(schema)

    files = sorted(DATA_DIR.glob("*.json"))
    violations: list[tuple[str, list[str]]] = []

    for path in files:
        data = json.loads(path.read_text())
        errors = sorted(validator.iter_errors(data), key=jsonschema.exceptions.relevance)
        if errors:
            violations.append((path.name, [e.message for e in errors]))

    if not violations:
        print(f"All {len(files)} files are valid.")
        return

    for filename, messages in violations:
        print(f"\n{filename}")
        for msg in messages:
            print(f"  - {msg}")

    sys.exit(1)


if __name__ == "__main__":
    main()
