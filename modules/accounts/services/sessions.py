"""Serviços de sessão e revogação de tokens JWT em cookies HttpOnly."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from user_agents import parse

from modules.accounts.authenticate import CustomAuthentication
from modules.accounts.models import UserSession


def revoke_sessions(user) -> None:
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    user.sessions.filter(is_active=True).update(is_active=False)
    active_tokens = list(
        OutstandingToken.objects.filter(
            user=user,
            expires_at__gt=timezone.now(),
            blacklistedtoken__isnull=True,
        )
    )
    if active_tokens:
        BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token=token) for token in active_tokens],
            ignore_conflicts=True,
        )


def revoke_session(session: UserSession) -> None:
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    token = OutstandingToken.objects.filter(jti=session.refresh_jti).first()
    if token:
        BlacklistedToken.objects.get_or_create(token=token)
    session.is_active = False
    session.save(update_fields=['is_active'])


def create_user_session(user, tokens: dict, *, user_agent: str = '', ip_address=None) -> UserSession:
    ua = parse(user_agent or '')
    return UserSession.objects.create(
        user=user,
        access_jti=AccessToken(tokens['access'])['jti'],
        refresh_jti=RefreshToken(tokens['refresh'])['jti'],
        device_name=f'{ua.browser.family} em {ua.os.family}'[:255],
        device_type='mobile' if ua.is_mobile else 'tablet' if ua.is_tablet else 'desktop',
        user_agent=(user_agent or '')[:1000],
        ip_address=ip_address,
        expires_at=timezone.now() + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
    )


@transaction.atomic
def refresh_user_session(raw_refresh_token: str | None) -> dict:
    if not raw_refresh_token:
        raise AuthenticationFailed('Refresh token ausente.')
    try:
        token = RefreshToken(raw_refresh_token)
        session = UserSession.objects.select_for_update(of=('self',)).for_refresh_jti(token['jti']).first()
        if not session:
            raise AuthenticationFailed('Sessão revogada ou inativa.')
        serializer = TokenRefreshSerializer(data={'refresh': raw_refresh_token})
        serializer.is_valid(raise_exception=True)
        tokens = serializer.validated_data
        session.access_jti = AccessToken(tokens['access'])['jti']
        session.refresh_jti = RefreshToken(tokens['refresh'])['jti']
        session.expires_at = timezone.now() + settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']
        session.save(update_fields=['access_jti', 'refresh_jti', 'expires_at', 'last_activity'])
    except TokenError as exc:
        raise InvalidToken('Token inválido ou expirado.') from exc
    return tokens


def logout_user_session(*, raw_access_token: str | None, raw_refresh_token: str | None) -> None:
    if raw_access_token:
        auth = CustomAuthentication()
        try:
            token = auth.get_validated_token(raw_access_token)
            session = UserSession.objects.filter(access_jti=token['jti']).first()
            if session:
                revoke_session(session)
        except (InvalidToken, TokenError):
            pass
    if raw_refresh_token:
        try:
            token = RefreshToken(raw_refresh_token)
            UserSession.objects.filter(refresh_jti=token['jti']).update(is_active=False)
            token.blacklist()
        except TokenError:
            pass
