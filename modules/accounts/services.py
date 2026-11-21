import logging
import secrets
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from user_agents import parse

from modules.accounts.authenticate import CustomAuthentication
from modules.accounts.hooks import run_deactivation_guards, run_deactivation_pre_locks
from modules.accounts.mixins.tokens import check_email_token, consume_email_token
from modules.accounts.models import EmailToken, UserSession
from shared.exceptions import get_or_not_found, require
from shared.geocoding import lookup_cep_brasilapi

logger = logging.getLogger(__name__)

EMAIL_SUBJECTS = {
    EmailToken.TokenType.NEW_PASSWORD: 'NextRouter - Código para redefinir sua senha',
    EmailToken.TokenType.NEW_USER: 'NextRouter - Código de verificação do cadastro',
    EmailToken.TokenType.NEW_EMAIL: 'NextRouter - Código de verificação do novo e-mail',
}


def generate_verification_code() -> str:
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def revoke_sessions(user):
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


def revoke_session(session):
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


def send_email_token(email, code, subject):
    minutes = getattr(settings, 'EMAIL_TOKEN_EXPIRATION_MINUTES', 15)
    body = (
        'Olá!\n\n'
        f'Seu código de verificação do NextRouter é: {code}\n\n'
        f'O código é válido por {minutes} minutos. Se você não solicitou este código, ignore este e-mail.\n'
    )
    message = EmailMessage(subject=subject, body=body, to=[email])
    try:
        message.send()
        return True
    except Exception as exc:
        logger.warning('email_token_delivery_failed reason=%s', type(exc).__name__)
        return False


def issue_email_token(*, email: str, token_type: str, user=None) -> bool:
    """Emite código de 6 dígitos respeitando anti-enumeração e cooldown.

    Retorna False apenas quando `NEW_EMAIL` falha na entrega SMTP (sinalizando 503).
    """
    if token_type == EmailToken.TokenType.NEW_EMAIL and (user is None or getattr(user, 'pk', None) is None):
        raise ValidationError({'detail': 'Usuário autenticado é obrigatório para troca de e-mail.'})

    user_model = get_user_model()
    exists = user_model.objects.by_email(email).exists()
    if (token_type == EmailToken.TokenType.NEW_PASSWORD and not exists) or (
        token_type in {EmailToken.TokenType.NEW_USER, EmailToken.TokenType.NEW_EMAIL} and exists
    ):
        return True

    if EmailToken.objects.in_cooldown(email=email, token_type=token_type).exists():
        return True

    code = generate_verification_code()
    token = EmailToken.objects.create(
        email=email,
        token_type=token_type,
        token_hash=make_password(code),
        user=user if token_type == EmailToken.TokenType.NEW_EMAIL else None,
    )
    # Envio SMTP fora de transação para evitar segurar conexão/locks em I/O de rede.
    if not send_email_token(email, code, EMAIL_SUBJECTS[token_type]):
        token.delete()
        return token_type != EmailToken.TokenType.NEW_EMAIL

    if token_type == EmailToken.TokenType.NEW_EMAIL:
        EmailToken.objects.filter(user=user, token_type=token_type).exclude(pk=token.pk).update(consumed=True)
    return True


def verify_email_change_code(*, user, code: str, password: str | None = None) -> EmailToken:
    """Valida código de troca de e-mail antes de verificar senha atual."""
    pending = EmailToken.objects.filter(user=user, token_type=EmailToken.TokenType.NEW_EMAIL).first()
    if not pending:
        raise ValidationError({'code': 'Código inválido ou inexistente.'})
    token = check_email_token(pending.email, code, EmailToken.TokenType.NEW_EMAIL, user)
    if password is not None and not user.check_password(password):
        raise ValidationError({'password': 'Senha atual incorreta.'})
    return token


@transaction.atomic
def reset_password_with_token(*, email: str, token: EmailToken, password: str) -> bool:
    user = get_user_model().objects.by_email(email).first()
    if not user:
        return False
    consume_email_token(token)
    user.set_password(password)
    user.save(update_fields=['password'])
    revoke_sessions(user)
    return True


@transaction.atomic
def confirm_email_change(*, user, token: EmailToken) -> None:
    consume_email_token(token)
    if get_user_model().objects.by_email(token.email).exclude(pk=user.pk).exists():
        raise ValidationError({'new_email': 'Já existe um usuário cadastrado com este e-mail.'})
    user.email = token.email
    user.save(update_fields=['email'])
    revoke_sessions(user)


def resolve_cep_coordinates(cep: str | None) -> tuple[float | None, float | None]:
    if not cep:
        return None, None
    cep_info = lookup_cep_brasilapi(cep)
    if cep_info and cep_info['latitude'] is not None and cep_info['longitude'] is not None:
        return cep_info['latitude'], cep_info['longitude']
    return None, None


def prepare_user_coords(validated_data: dict, *, instance=None) -> dict:
    """Resolve coordenadas via CEP antes de abrir qualquer transação de banco."""
    data = dict(validated_data)
    if instance is None:
        has_coords = data.get('latitude') is not None and data.get('longitude') is not None
        if has_coords:
            data['geocoded_at'] = timezone.now()
        else:
            data.pop('latitude', None)
            data.pop('longitude', None)
            lat, lon = resolve_cep_coordinates(data.get('cep'))
            if lat is not None and lon is not None:
                data['latitude'] = lat
                data['longitude'] = lon
                data['geocoded_at'] = timezone.now()
        return data

    new_cep = data.get('cep')
    missing_coords = instance.latitude is None or instance.longitude is None
    should_geocode = 'cep' in data and bool(new_cep) and (new_cep != instance.cep or missing_coords)
    if should_geocode:
        lat, lon = resolve_cep_coordinates(new_cep)
        if lat is not None and lon is not None:
            data['latitude'] = lat
            data['longitude'] = lon
            data['geocoded_at'] = timezone.now()
    return data


def create_user_account(validated_data: dict, *, token_instance: EmailToken, coords_prepared: bool = False):
    data = dict(validated_data) if coords_prepared else prepare_user_coords(validated_data)
    data.pop('code', None)
    pic_instance = data.pop('profile_picture', None)

    with transaction.atomic():
        consume_email_token(token_instance)
        if pic_instance:
            # A descrição da foto é exibida para outros usuários: não incluir o CPF.
            pic_instance.description = f'Foto de {data.get("name", "")}'
            pic_instance.save(update_fields=['description'])
        return get_user_model().objects.create_user(**data, profile_picture=pic_instance)


def update_user_account(instance, validated_data: dict, *, coords_prepared: bool = False):
    data = dict(validated_data) if coords_prepared else prepare_user_coords(validated_data, instance=instance)

    with transaction.atomic():
        old_pic_to_delete = None
        if 'profile_picture' in data:
            new_pic_instance = data.pop('profile_picture')
            old_pic_instance = instance.profile_picture
            if old_pic_instance and old_pic_instance != new_pic_instance:
                old_pic_to_delete = old_pic_instance
            if new_pic_instance:
                new_pic_instance.description = f'Foto de {data.get("name", instance.name)}'
                new_pic_instance.save(update_fields=['description'])
            instance.profile_picture = new_pic_instance

        for attr, value in data.items():
            setattr(instance, attr, value)

        instance.save()
        if old_pic_to_delete is not None:
            transaction.on_commit(old_pic_to_delete.delete)

    return instance


@transaction.atomic
def guard_account_deactivation(*, user_id):
    # Ordem de locks preservada: empresas (via pre_lock) antes de usuários.
    run_deactivation_pre_locks(user_id)
    users = list(
        get_user_model()
        .objects.select_for_update()
        .filter(Q(pk=user_id) | Q(is_staff=True, is_active=True))
        .order_by('pk')
    )
    require(any(user.pk == user_id for user in users), 'not_found', 'Conta não encontrada.')
    target = next(user for user in users if user.pk == user_id)
    require(
        not (target.is_staff and target.is_active) or sum(user.is_staff and user.is_active for user in users) > 1,
        'last_staff',
        'Não é possível desativar o último administrador ativo.',
    )
    run_deactivation_guards(user_id)
    return target


@transaction.atomic
def deactivate_account(*, actor_id, user_id):
    user_model = get_user_model()
    actor = get_or_not_found(user_model.objects.active(), pk=actor_id)
    require(actor_id == user_id or actor.is_staff, 'permission_denied', 'Desativação não autorizada.')
    user = guard_account_deactivation(user_id=user_id)
    user.deactivate()
    revoke_sessions(user)
    return user
