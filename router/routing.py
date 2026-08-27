from django.urls import re_path

from router.consumers import TravelLocationConsumer

websocket_urlpatterns = [
    re_path(r'^ws/travels/(?P<travel_id>\d+)/location/$', TravelLocationConsumer.as_asgi()),
]
