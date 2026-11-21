import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserSessionQuerySet(models.QuerySet):
    def active(self, *, now=None):
        moment = now or timezone.now()
        return self.filter(is_active=True, user__is_active=True, expires_at__gt=moment)

    def for_access_jti(self, jti: str, *, user_id, now=None):
        if not jti or not user_id:
            return self.none()
        return self.active(now=now).filter(access_jti=jti, user_id=user_id)

    def for_refresh_jti(self, jti: str, *, now=None):
        return self.active(now=now).filter(refresh_jti=jti)

    def with_user(self):
        return self.select_related('user')


class UserSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sessions')

    access_jti = models.CharField(max_length=255, db_index=True)
    refresh_jti = models.CharField(max_length=255, unique=True)

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

    objects = UserSessionQuerySet.as_manager()

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=['user', 'is_active']),
            models.Index(
                fields=['user', 'access_jti', 'is_active', 'expires_at'],
                name='session_user_jti_active_idx',
            ),
        ]
        ordering: ClassVar[list[str]] = ['-last_activity']

    def __str__(self) -> str:
        return f'Sessão {self.id} ({self.device_name})'
