import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models


class UserSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')

    access_jti = models.CharField(max_length=255, db_index=True)
    refresh_jti = models.CharField(max_length=255, unique=True, db_index=True)

    device_name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=20, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=50, blank=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=['user', 'is_active'])]
        ordering: ClassVar[list[str]] = ['-last_activity']

    def __str__(self) -> str:
        return f'Sessão {self.id} ({self.device_name})'
