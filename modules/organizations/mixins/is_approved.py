import logging
from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache
from django.core.mail import EmailMessage
from django.db import close_old_connections, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from modules.organizations.models.driver import Driver
from modules.organizations.models.passenger import Passenger
from modules.organizations.permissions import IsCompanyOwner
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED, RESP_403_FORBIDDEN, RESP_404_NOT_FOUND

logger = logging.getLogger(__name__)

_APPROVAL_EMAIL_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix='approval-email')
_PROFILE_MODELS = {
    'passenger': Passenger,
    'driver': Driver,
}


def _approval_cache_key(model_name: str, pk: int, route_group_id: int) -> str:
    return f'approval_email:{model_name}:{pk}:{route_group_id}'


def clear_approval_notification_key(instance, route_group_id=None):
    group_id = route_group_id if route_group_id is not None else getattr(instance, 'route_group_id', None)
    if instance.pk and group_id:
        cache.delete(_approval_cache_key(instance._meta.model_name, instance.pk, group_id))


def _send_approval_email_task(model_name: str, pk: int, route_group_id: int):
    close_old_connections()
    model_cls = _PROFILE_MODELS.get(model_name)
    if model_cls is None:
        return

    cache_key = _approval_cache_key(model_name, pk, route_group_id)
    if not cache.add(cache_key, True, timeout=86400):
        return

    try:
        instance = (
            model_cls.objects
            .select_related('user', 'route_group', 'route_group__company')
            .filter(pk=pk, route_group_id=route_group_id, is_approved=True, is_rejected=False)
            .first()
        )
        if not instance or not instance.user.email or not instance.route_group:
            return

        role_label = 'passageiro' if model_name == 'passenger' else 'motorista'
        group_name = instance.route_group.name
        company_name = instance.route_group.company.trade_name
        subject = f'NextRouter - Vínculo aprovado na rota {group_name}'
        body = (
            f'Olá, {instance.user.name}!\n\n'
            f'Seu vínculo como {role_label} no grupo de rota "{group_name}" '
            f'da empresa "{company_name}" foi aprovado.\n\n'
            'Você já pode acessar os recursos do grupo na plataforma NextRouter.\n'
        )
        EmailMessage(subject=subject, body=body, to=[instance.user.email]).send()
        logger.info('approval_email_sent model=%s profile_id=%s group_id=%s', model_name, pk, route_group_id)
    except Exception as exc:
        logger.warning(
            'approval_email_failed model=%s profile_id=%s reason=%s',
            model_name,
            pk,
            type(exc).__name__,
        )


def dispatch_approval_email_on_commit(instance):
    if not instance.pk or not instance.route_group_id:
        return
    model_name = instance._meta.model_name
    pk = instance.pk
    route_group_id = instance.route_group_id

    def _enqueue():
        try:
            future = _APPROVAL_EMAIL_EXECUTOR.submit(_send_approval_email_task, model_name, pk, route_group_id)
            future.result(timeout=0.05)
        except Exception:
            pass

    transaction.on_commit(_enqueue, robust=True)


class ApproveProfileMixin:
    @extend_schema(
        request=None,
        tags=['Vínculos'],
        summary='Aprove o vínculo',
        description=(
            'Somente empresa aprovada dona do grupo aprova motorista ou aluno vinculado; '
            'notifica por e-mail após commit. Repetição é idempotente.'
        ),
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                },
            },
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            404: RESP_404_NOT_FOUND,
        },
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsCompanyOwner])
    @transaction.atomic
    def approve(self, request, pk=None):
        instance = self.get_object()
        instance = type(instance).objects.select_for_update().get(pk=instance.pk)
        self.check_object_permissions(request, instance)
        if not instance.route_group_id:
            return Response(
                {'detail': 'O perfil não está vinculado a um grupo de rota.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        was_approved = instance.is_approved and not instance.is_rejected
        if not was_approved:
            instance.is_approved = True
            instance.is_rejected = False
            instance.save(update_fields=['is_approved', 'is_rejected'])
            dispatch_approval_email_on_commit(instance)

        return Response(
            {
                'message': 'Aprovado com sucesso.',
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=['Vínculos'],
        summary='Recuse o vínculo',
        description=(
            'Somente empresa aprovada dona do grupo. Recusa motorista ou aluno; '
            'desassocia veículo do motorista recusado.'
        ),
        request=None,
        responses={
            200: {'type': 'object', 'properties': {'message': {'type': 'string'}}},
            400: RESP_400_VALIDATION,
            401: RESP_401_UNAUTHORIZED,
            403: RESP_403_FORBIDDEN,
            404: RESP_404_NOT_FOUND,
        },
    )
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated, IsCompanyOwner])
    @transaction.atomic
    def reject(self, request, pk=None):
        instance = self.get_object()
        instance = type(instance).objects.select_for_update().get(pk=instance.pk)
        self.check_object_permissions(request, instance)
        if not instance.route_group_id:
            return Response(
                {'detail': 'O perfil não está vinculado a um grupo de rota.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        clear_approval_notification_key(instance)
        instance.is_approved = False
        instance.is_rejected = True
        instance.save(update_fields=['is_approved', 'is_rejected'])
        if isinstance(instance, Driver):
            from modules.transport.models.vehicle import Vehicle

            Vehicle.objects.filter(driver=instance, route_group_id=instance.route_group_id).update(driver=None)
        return Response({'message': 'Recusado com sucesso.'})
