"""
Writes the secrets for the local Langfuse (langfuse/.env) and points the copilot at it (.env).
Both files are gitignored. Runs once; later runs keep the existing values. Prints no secrets.
"""

import secrets
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LF_ENV, APP_ENV = REPO / "langfuse" / ".env", REPO / ".env"


def read(path: Path) -> dict:
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs}


def main() -> None:
    lf = read(LF_ENV)
    if not lf:
        lf = {"POSTGRES_PASSWORD": secrets.token_hex(16), "CLICKHOUSE_PASSWORD": secrets.token_hex(16),
              "MINIO_ROOT_PASSWORD": secrets.token_hex(16), "REDIS_AUTH": secrets.token_hex(16),
              "SALT": secrets.token_hex(16), "ENCRYPTION_KEY": secrets.token_hex(32),
              "NEXTAUTH_SECRET": secrets.token_hex(32), "LANGFUSE_ADMIN_PASSWORD": secrets.token_urlsafe(12),
              "LANGFUSE_PUBLIC_KEY": f"pk-lf-{secrets.token_hex(16)}",
              "LANGFUSE_SECRET_KEY": f"sk-lf-{secrets.token_hex(16)}"}
        LF_ENV.write_text("# Local Langfuse secrets, written by scripts/langfuse_setup.py. Never commit.\n"
                          + "".join(f"{k}={v}\n" for k, v in lf.items()))
        print(f"wrote {LF_ENV.relative_to(REPO)}")
    app = read(APP_ENV)
    add = {"LANGFUSE_PUBLIC_KEY": lf["LANGFUSE_PUBLIC_KEY"], "LANGFUSE_SECRET_KEY": lf["LANGFUSE_SECRET_KEY"],
           "LANGFUSE_BASE_URL": "http://localhost:3000"}
    missing = {k: v for k, v in add.items() if k not in app}
    if missing:
        with APP_ENV.open("a") as f:
            f.write("\n# Local Langfuse (make langfuse-up)\n" + "".join(f"{k}={v}\n" for k, v in missing.items()))
        print(f"added {', '.join(missing)} to .env")
    print("Langfuse UI: http://localhost:3000  login: admin@localhost.test, password: LANGFUSE_ADMIN_PASSWORD in langfuse/.env")


if __name__ == "__main__":
    main()
