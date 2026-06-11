"""DEPRECATED compatibility shim.

Moved to ``leapconnect.application.notification_dispatcher``.
"""

from leapconnect.application.notification_dispatcher import *  # noqa: F401,F403
from leapconnect.application.notification_dispatcher import (  # noqa: F401
    NotificationDispatcher,
    _geofence_contains,
)
from leapconnect.domain.notifications.event_catalog import (  # noqa: F401
    EVENT_CATALOG,
    EVENT_CATALOG_MAP,
    IMAGE_ENABLED_BY_DEFAULT_EVENTS,
    MESSAGE_TEMPLATES,
    TRANSITION_EVENTS,
)
from leapconnect.domain.notifications.geofencing import (  # noqa: F401
    haversine_distance_m,
    point_in_polygon,
)
