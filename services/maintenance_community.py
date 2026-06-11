"""DEPRECATED compatibility shim.

Moved to ``leapconnect.infrastructure.community``.
"""

from leapconnect.infrastructure.community import *  # noqa: F401,F403
from leapconnect.infrastructure.community import (  # noqa: F401
    CommunityError,
    discover_repo,
    fetch_pack_file,
    fetch_pack_url,
    parse_github_url,
)
