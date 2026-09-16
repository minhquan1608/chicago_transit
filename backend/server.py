from __future__ import annotations

import os
import sys

from backend.api.config import Settings

def main() -> None:
    settings = Settings.from_env()
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(settings.serve_port),
        ],
    )

if __name__ == "__main__":
    main()
