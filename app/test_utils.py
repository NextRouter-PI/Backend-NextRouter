"""Utilitários compartilhados pelos testes automatizados (`pdm run test`)."""

import io
import itertools
import re
import shutil
import tempfile
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image as PILImage
from rest_framework import status
from rest_framework.test import APITestCase

from authenticator.management.commands.backfill_user_data import _placeholder_pdf
from authenticator.management.commands.seed_demo_data import make_cnpj, make_cpf
from authenticator.models import Company, CompanyRouteGroup, Driver, Passenger, User

PASSWORD = 'SenhaForte@123'

_sequence = itertools.count(100)


def unique_cpf():
    return make_cpf(f'{next(_sequence):09d}')


def masked_cpf():
    cpf = unique_cpf()
    return f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'


def unique_cnpj():
    return make_cnpj(f'{next(_sequence):08d}0001')


def png_file(name='foto.png'):
    buffer = io.BytesIO()
    PILImage.new('RGB', (10, 10), color='blue').save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def pdf_file(name='documento.pdf'):
    return SimpleUploadedFile(name, _placeholder_pdf('Documento').read(), content_type='application/pdf')


def create_user(email, **extra):
    defaults = {'name': email.split('@')[0], 'cpf': unique_cpf()}
    defaults.update(extra)
    return User.objects.create_user(email=email, password=PASSWORD, **defaults)


def create_company(email, *, approved=True):
    return Company.objects.create(
        user=create_user(email),
        trade_name=f'Empresa {email}',
        legal_name=f'Empresa {email} LTDA',
        cnpj=unique_cnpj(),
        state_registration='123456789',
        is_approved=approved,
    )


def create_route_group(company, name='Rota Centro'):
    return CompanyRouteGroup.objects.create(company=company, name=name, common_cep='89010-000')


def create_driver(email, route_group=None, *, approved=True):
    return Driver.objects.create(user=create_user(email), route_group=route_group, is_approved=approved)


def create_passenger(email, route_group=None, *, approved=True):
    return Passenger.objects.create(user=create_user(email), route_group=route_group, is_approved=approved)


class BaseAPITestCase(APITestCase):
    """
    Desliga a geocodificação (chamada de rede ao Nominatim), limpa o cache de throttling
    e salva os arquivos enviados numa pasta temporária em vez de /media.
    """

    def setUp(self):
        super().setUp()
        cache.clear()

        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=media_root)
        media_override.enable()
        self.addCleanup(media_override.disable)

        for target in ('authenticator.geocoding_mixin.geocode_address', 'router.services.geocode_address'):
            patcher = mock.patch(target, return_value=(-26.3, -48.8))
            patcher.start()
            self.addCleanup(patcher.stop)

    def request_code(self, email, token_type='new-user'):
        """Pede o código como o front-end faz e devolve o código lido do e-mail enviado."""
        mail.outbox.clear()
        response = self.client.post(
            '/api/email-tokens/send-email/', {'email': email, 'token_type': token_type}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)
