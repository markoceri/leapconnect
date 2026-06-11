"""LeapConnect entrypoint.

The application now lives in the ``leapconnect`` package (hexagonal layout):

- ``leapconnect.api.app``  — FastAPI app factory and routers
- ``leapconnect.container`` — composition root (state + service wiring)
- ``leapconnect.domain`` / ``leapconnect.application`` / ``leapconnect.infrastructure``

This module remains the uvicorn target (``main:app``) and the CLI entrypoint.
"""

from __future__ import annotations

from leapconnect.api.app import app  # noqa: F401  (uvicorn target: main:app)


def _cli_reset_password(new_password: str) -> None:
    """Reset the LeapConnect user password from the command line."""
    import asyncio

    from leapconnect.config import database_url
    from leapconnect.infrastructure.persistence.sqlite_adapter import (
        SqlAlchemyRepository,
    )

    if len(new_password) < 4:
        print("Error: Password must be at least 4 characters")
        raise SystemExit(1)

    async def _reset():
        repo = SqlAlchemyRepository(database_url())
        await repo.init_db()
        user = await repo.get_user()
        if not user:
            print("Error: No user account found. Nothing to reset.")
            return False
        await repo.update_user(password=new_password)
        print(f"Password reset successfully for user '{user['display_name']}'.")
        return True

    success = asyncio.run(_reset())
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    import sys

    import uvicorn

    if len(sys.argv) >= 2 and sys.argv[1] == "--reset-password":
        if len(sys.argv) < 3:
            print("Usage: python main.py --reset-password <new_password>")
            raise SystemExit(1)
        _cli_reset_password(sys.argv[2])
    else:
        uvicorn.run(app, host="0.0.0.0", port=8099)
