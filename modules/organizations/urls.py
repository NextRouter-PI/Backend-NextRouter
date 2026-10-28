from django.urls import path
from rest_framework.routers import SimpleRouter

from .api.views.company import CompanyViewSet
from .api.views.company_route_group import CompanyGroupRouteViewSet
from .api.views.driver import DriverViewSet
from .api.views.passenger import PassengerViewSet
from .api.views.registration import RegistrationConfirmView

router = SimpleRouter()
router.register('passengers', PassengerViewSet, basename='passengers')
router.register('drivers', DriverViewSet, basename='drivers')
router.register('companies', CompanyViewSet, basename='companies')
router.register('company-route-groups', CompanyGroupRouteViewSet, basename='company-route-groups')

urlpatterns = [path('registration/confirm/', RegistrationConfirmView.as_view())]
