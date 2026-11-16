"""Utilitários compartilhados pelos testes automatizados (`pdm run test`)."""

import io
import itertools
import re
import shutil
import tempfile

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image as PILImage
from rest_framework import status
from rest_framework.test import APITestCase

from modules.accounts.models import User
from modules.organizations.models import Company, CompanyRouteGroup, OperationalPoint, Passenger
from shared.demo import make_cnpj, make_cpf, placeholder_pdf

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
    return SimpleUploadedFile(name, placeholder_pdf('Documento').read(), content_type='application/pdf')


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
    return CompanyRouteGroup.objects.create(company=company, name=name)


def create_passenger(email):
    return Passenger.objects.create(user=create_user(email))


def create_operational_point(company, **extra):
    defaults = {
        'company': company,
        'name': 'Ponto fictício',
        'street': 'Rua Fictícia',
        'number': '100',
        'neighborhood': 'Centro',
        'city': 'Blumenau',
        'state': 'SC',
        'cep': '89010-000',
        'latitude': -26.3,
        'longitude': -48.8,
        'created_by': company.user,
    }
    defaults.update(extra)
    return OperationalPoint.objects.create(**defaults)


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
        private_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, private_root, ignore_errors=True)
        media_override = override_settings(MEDIA_ROOT=media_root, PRIVATE_DOCUMENT_ROOT=private_root)
        media_override.enable()
        self.addCleanup(media_override.disable)

    def request_code(self, email, token_type='new-user'):
        """Pede o código como o front-end faz e devolve o código lido do e-mail enviado."""
        mail.outbox.clear()
        response = self.client.post(
            '/api/email-tokens/send-email/', {'email': email, 'token_type': token_type}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)
