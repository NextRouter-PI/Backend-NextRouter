from .base import ConfigurationViewSet
from .groups import GroupViewSet
from .habitual_routes import HabitualRouteViewSet
from .points import PointViewSet
from .policies import PolicyViewSet
from .services import ServiceViewSet
from .vehicles import VehicleViewSet

__all__ = [
    'ConfigurationViewSet',
    'GroupViewSet',
    'HabitualRouteViewSet',
    'PointViewSet',
    'PolicyViewSet',
    'ServiceViewSet',
    'VehicleViewSet',
]
