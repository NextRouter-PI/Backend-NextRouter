from rest_framework.routers import SimpleRouter

from .api.views.company_route_schedule import CompanyRouteScheduleViewSet
from .api.views.confirm_passenger_route import ConfirmPassengerRouteViewSet
from .api.views.driver_rating import DriverRatingViewSet
from .api.views.lost_item import LostItemViewSet
from .api.views.path import PathViewSet
from .api.views.travel import TravelViewSet
from .api.views.vehicle import VehicleViewSet

router = SimpleRouter()
router.register('route-schedules', CompanyRouteScheduleViewSet, basename='route-schedules')
router.register('confirmations', ConfirmPassengerRouteViewSet, basename='confirmations')
router.register('lost-items', LostItemViewSet, basename='lost-items')
router.register('paths', PathViewSet, basename='paths')
router.register('vehicles', VehicleViewSet, basename='vehicles')
router.register('travels', TravelViewSet, basename='travels')
router.register('driver-ratings', DriverRatingViewSet, basename='driver-ratings')

urlpatterns = []
