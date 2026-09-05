#!/usr/bin/env python
"""Entry point script to run the WebsiteCMS application."""

import uvicorn

from app.config import get_settings


def main():
    """Run the application using uvicorn."""
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
