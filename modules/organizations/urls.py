from django.urls import path
from rest_framework.routers import SimpleRouter

from .api.views.company import CompanyViewSet
from .api.views.membership import GroupMembershipViewSet, MembershipEventViewSet, MembershipViewSet
from .api.views.profile import DriverViewSet, PassengerViewSet
from .api.views.registration import RegistrationConfirmView

router = SimpleRouter()
router.register('passengers', PassengerViewSet, basename='passengers')
router.register('drivers', DriverViewSet, basename='drivers')
router.register('companies', CompanyViewSet, basename='companies')
router.register('memberships', MembershipViewSet, basename='memberships')
router.register('membership-events', MembershipEventViewSet, basename='membership-events')
router.register('group-memberships', GroupMembershipViewSet, basename='group-memberships')

urlpatterns = [path('registration/confirm/', RegistrationConfirmView.as_view())]
