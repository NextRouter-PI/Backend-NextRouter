from core.views.user import UserViewSet
from core.views.passenger import PassengerViewSet
from core.views.driver import DriverViewSet
from core.views.company import CompanyViewSet
from core.views.company_route_group import CompanyGroupRouteViewSet
from core.views.auth import (
    CustomLogoutView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
)
from core.views.confirm_passenger_route import ConfirmPassengerRouteViewSet
from core.views.lost_item import LostItemViewSet
from core.views.path import PathViewSet
from core.views.vehicle import VehicleViewSet