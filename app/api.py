from django.urls import include, path
from rest_framework.routers import DefaultRouter

from modules.accounts import urls as accounts
from modules.organizations import urls as organizations
from modules.transport import urls as transport

router = DefaultRouter()
router.registry.extend(accounts.router.registry)
router.registry.extend(organizations.router.registry)
router.registry.extend(transport.router.registry)

urlpatterns = [
    *accounts.urlpatterns,
    *organizations.urlpatterns,
    *transport.urlpatterns,
    path('', include(router.urls)),
    path('uploads/', include('modules.uploads.urls')),
]
