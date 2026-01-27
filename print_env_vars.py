import os
from pathlib import Path


def _mask(value: str | None) -> str:
    if value is None:
        return "<MISSING>"
    s = str(value)
    if not s:
        return "<EMPTY>"
    if len(s) <= 10:
        return "<SET>"
    return f"{s[:6]}...{s[-4:]}"


def _read_dotenv(dotenv_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not dotenv_path.exists():
        return data

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]
        if key:
            data[key] = value

    return data


def main() -> None:
    dotenv_path = Path(__file__).resolve().parent / ".env"
    dotenv_values = _read_dotenv(dotenv_path)

    keys = [
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "ORCHESTRATOR_TIMEOUT_SECONDS",
        "BILLING_COST_LIMIT_USD",
        "PROMPT_MAX_REPLY_TOKENS",
        "PROMPT_INCLUDE_REASONING",
        "PROMPT_USE_COMPACT_SCHEMAS",
        "LLM_DEFAULT_PROVIDER",
        "LLM_PREMIUM_MODEL",
    ]

    print(f".env exists: {dotenv_path.exists()}  path={dotenv_path}")
    print("\nKey\tIN os.environ\tIN .env")
    print("-" * 80)

    for key in keys:
        env_val = os.environ.get(key)
        file_val = dotenv_values.get(key)

        if key.endswith("_KEY") or key.endswith("_TOKEN") or "API_KEY" in key:
            env_show = _mask(env_val)
            file_show = _mask(file_val)
        else:
            env_show = "<MISSING>" if env_val is None else (env_val if env_val != "" else "<EMPTY>")
            file_show = "<MISSING>" if file_val is None else (file_val if file_val != "" else "<EMPTY>")

        print(f"{key}\t{env_show}\t{file_show}")


if __name__ == "__main__":
    main()
