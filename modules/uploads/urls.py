from rest_framework.routers import DefaultRouter

from modules.uploads.api import views

app_name = 'uploader'

router = DefaultRouter()
router.register('images', views.ImageUploadViewSet)
router.register('documents', views.DocumentUploadViewSet)

urlpatterns = router.urls
