from __future__ import annotations

import os
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class LocalEnvError(ValueError):
    pass


def default_env_path() -> Path:
    configured_path = os.getenv("SERVICE_DESK_ENV_PATH")
    return Path(configured_path) if configured_path else REPO_ROOT / ".env"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    elif " #" in value:
        value = value.split(" #", 1)[0].rstrip()

    return key, value


def load_local_env(path: Path | None = None) -> None:
    env_path = path or default_env_path()
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)


def set_local_env_value(key: str, value: str, path: Path | None = None) -> Path:
    env_key = key.strip()
    if not ENV_NAME_PATTERN.fullmatch(env_key):
        raise LocalEnvError("Имя переменной окружения должно содержать латиницу, цифры и _, начинаться с буквы или _.")
    if value == "":
        raise LocalEnvError("Пустое значение секрета не сохраняется.")

    env_path = path or default_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated_lines: list[str] = []
    updated = False

    for line in lines:
        parsed = _parse_env_line(line)
        if parsed and parsed[0] == env_key:
            if not updated:
                updated_lines.append(f"{env_key}={_format_env_value(value)}")
                updated = True
            continue
        updated_lines.append(line)

    if not updated:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append(f"{env_key}={_format_env_value(value)}")

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    os.environ[env_key] = value
    return env_path


def _format_env_value(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:@+=,-]+", value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
