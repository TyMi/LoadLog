import logging
import os

import uvicorn

from .api import create_app, exposure_warning


def main() -> None:
    if (hint := exposure_warning()) is not None:
        logging.getLogger("uvicorn.error").warning(hint)
    uvicorn.run(create_app(), host=os.environ.get("LOADLOG_HOST", "127.0.0.1"),  # ohne Login nie von selbst offen; im Container setzt das Dockerfile 0.0.0.0
                port=int(os.environ.get("LOADLOG_PORT", "8080")), log_level="info")


if __name__ == "__main__":
    main()
