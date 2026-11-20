from rest_framework.routers import SimpleRouter

from .api.views.configuration import (
    GroupViewSet,
    HabitualRouteViewSet,
    PointViewSet,
    PolicyViewSet,
    ServiceViewSet,
    VehicleViewSet,
)
from .api.views.daily import ChangeRequestViewSet, DayViewSet, EligibilityViewSet, ResponseViewSet
from .api.views.history import LostItemViewSet, RatingViewSet
from .api.views.operation import (
    EventViewSet,
    InvitationViewSet,
    JobViewSet,
    NotificationViewSet,
    ParticipantViewSet,
    PublicationViewSet,
    SnapshotViewSet,
    StopViewSet,
    TravelViewSet,
)

router = SimpleRouter()
router.register('operational-points', PointViewSet, basename='operational-points')
router.register('company-route-groups', GroupViewSet, basename='company-route-groups')
router.register('habitual-routes', HabitualRouteViewSet, basename='habitual-routes')
router.register('response-policies', PolicyViewSet, basename='response-policies')
router.register('recurring-services', ServiceViewSet, basename='recurring-services')
router.register('service-days', DayViewSet, basename='service-days')
router.register('eligibilities', EligibilityViewSet, basename='eligibilities')
router.register('daily-responses', ResponseViewSet, basename='daily-responses')
router.register('change-requests', ChangeRequestViewSet, basename='change-requests')
router.register('vehicles', VehicleViewSet, basename='vehicles')
router.register('travels', TravelViewSet, basename='travels')
router.register('travel-participations', ParticipantViewSet, basename='travel-participations')
router.register('participation-events', EventViewSet, basename='participation-events')
router.register('route-snapshots', SnapshotViewSet, basename='route-snapshots')
router.register('route-stops', StopViewSet, basename='route-stops')
router.register('travel-publications', PublicationViewSet, basename='travel-publications')
router.register('driver-invitations', InvitationViewSet, basename='driver-invitations')
router.register('notifications', NotificationViewSet, basename='notifications')
router.register('optimization-jobs', JobViewSet, basename='optimization-jobs')
router.register('driver-ratings', RatingViewSet, basename='driver-ratings')
router.register('lost-items', LostItemViewSet, basename='lost-items')

urlpatterns = []
