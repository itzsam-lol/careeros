"""Write the API's OpenAPI schema to a file (input for the generated TypeScript client).

uv run python -m careeros.tools.export_openapi ../../packages/api-client/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from careeros.config import Settings
from careeros.main import create_app


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    app = create_app(Settings(_env_file=None, log_level="WARNING"))
    schema = app.openapi()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(schema, indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n"
    )
    sys.stdout.write(f"wrote {len(schema.get('paths', {}))} paths to {target}\n")


if __name__ == "__main__":
    main()
