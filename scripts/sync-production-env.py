"""Merge local application settings into production without breaking infra."""

import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set


# These values are generated for or wired by the production Compose stack.
# Local variants commonly point at localhost and must never replace them.
PROTECTED_KEYS = {
    "ALLOW_DEV_AUTH_BYPASS",
    "AUTH_JWT_SECRET",
    "CODE_EXECUTION_API_URL",
    "DATABASE_URL",
    "POSTGRES_DB",
    "POSTGRES_PASSWORD",
    "POSTGRES_USER",
    "REDIS_URL",
    "STORAGE_ROOT",
    "TASK_QUEUE_BACKEND",
    "TASK_QUEUE_NAME",
    "VITE_SERVER_URL",
}


def read_env(path: Path) -> Dict[str, str]:
    values = {}  # type: Dict[str, str]
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in PROTECTED_KEYS:
            values[key] = value
    return values


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: sync-production-env.py SOURCE TARGET")

    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    incoming = read_env(source)
    if not incoming:
        raise SystemExit("source contains no deployable application settings")

    original_lines = target.read_text(encoding="utf-8").splitlines()
    rendered = []  # type: List[str]
    updated = set()  # type: Set[str]
    for line in original_lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else ""
        if key in incoming:
            rendered.append(f"{key}={incoming[key]}")
            updated.add(key)
        else:
            rendered.append(line)

    missing = sorted(set(incoming) - updated)
    if missing:
        rendered.extend(["", "# Application integrations synced for production"])
        rendered.extend(f"{key}={incoming[key]}" for key in missing)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup = target.with_name(f"{target.name}.backup.{stamp}")
    shutil.copy2(target, backup)
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text("\n".join(rendered) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    print(
        f"Updated {len(incoming)} application settings; "
        f"preserved {len(PROTECTED_KEYS)} production-only settings; "
        f"backup={backup}"
    )


if __name__ == "__main__":
    main()
