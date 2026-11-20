"""Popula o banco de desenvolvimento local com dados fictícios para homologação (Marco A/B)."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from modules.accounts.models import User
from modules.organizations.models import Company, CompanyRouteGroup, Driver, OperationalPoint, Passenger
from shared.demo import make_cnpj, make_cpf

DEV_PASSWORD = 'SenhaForte@123'
ADMIN_PASSWORD = 'Admin@12345'


def _ensure_user(email, *, name, cpf, password, is_staff=False, is_superuser=False):
    user = User.objects.filter(email=email).first()
    if user is not None:
        return user, False

    if is_superuser:
        user = User.objects.create_superuser(email=email, password=password, name=name, cpf=cpf)
    else:
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            cpf=cpf,
            is_staff=is_staff,
        )
    return user, True


class Command(BaseCommand):
    help = 'Cria dados fictícios e idempotentes para homologação local (somente com DEBUG=True).'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('seed_homologacao só pode ser executado em ambiente de desenvolvimento (DEBUG=True).')

        admin_user, admin_created = _ensure_user(
            'admin@nextrouter.local',
            name='Administrador Local',
            cpf=make_cpf('900000001'),
            password=ADMIN_PASSWORD,
            is_staff=True,
            is_superuser=True,
        )

        company_user, _ = _ensure_user(
            'empresa@nextrouter.local',
            name='SuperTransporte Gestor',
            cpf=make_cpf('900000002'),
            password=DEV_PASSWORD,
        )
        supertransporte, st_created = Company.objects.get_or_create(
            user=company_user,
            defaults={
                'trade_name': 'SuperTransporte',
                'legal_name': 'SuperTransporte Escolar Fictícia LTDA',
                'cnpj': make_cnpj('900000010001'),
                'state_registration': '123456789',
                'contact_phone': '47999990001',
                'contact_email': 'contato@supertransporte.local',
                'cep': '89201000',
                'street': 'Rua do Príncipe',
                'number': '100',
                'neighborhood': 'Centro',
                'city': 'Joinville',
                'state': 'SC',
                'is_approved': True,
            },
        )
        if not supertransporte.is_approved:
            supertransporte.is_approved = True
            supertransporte.save(update_fields=['is_approved'])

        garage_point, _ = OperationalPoint.objects.get_or_create(
            company=supertransporte,
            name='Garagem Central Joinville',
            defaults={
                'point_type': OperationalPoint.PointType.GARAGE,
                'street': 'Rua XV de Novembro',
                'number': '500',
                'neighborhood': 'Centro',
                'city': 'Joinville',
                'state': 'SC',
                'cep': '89201600',
                'latitude': -26.3044,
                'longitude': -48.8455,
                'created_by': company_user,
            },
        )

        dest_point, _ = OperationalPoint.objects.get_or_create(
            company=supertransporte,
            name='IFC Campus Araquari',
            defaults={
                'point_type': OperationalPoint.PointType.DESTINATION,
                'street': 'BR-280, km 27',
                'number': 'S/N',
                'neighborhood': 'Colégio Agrícola',
                'city': 'Araquari',
                'state': 'SC',
                'cep': '89245000',
                'latitude': -26.3941,
                'longitude': -48.7385,
                'created_by': company_user,
            },
        )

        CompanyRouteGroup.objects.get_or_create(
            company=supertransporte,
            name='IFC Araquari — Manhã',
            defaults={'destination': dest_point},
        )

        pending_user, _ = _ensure_user(
            'pendente@nextrouter.local',
            name='NovaTransporte Gestor',
            cpf=make_cpf('900000003'),
            password=DEV_PASSWORD,
        )
        pending_company, pending_created = Company.objects.get_or_create(
            user=pending_user,
            defaults={
                'trade_name': 'NovaTransporte',
                'legal_name': 'NovaTransporte Fictícia LTDA',
                'cnpj': make_cnpj('900000020001'),
                'state_registration': '987654321',
                'contact_phone': '47999990002',
                'contact_email': 'contato@novatransporte.local',
                'cep': '89201000',
                'street': 'Avenida Juscelino Kubitschek',
                'number': '250',
                'neighborhood': 'Centro',
                'city': 'Joinville',
                'state': 'SC',
                'is_approved': False,
            },
        )

        passenger_user, _ = _ensure_user(
            'passageiro@nextrouter.local',
            name='Ana Souza',
            cpf=make_cpf('900000004'),
            password=DEV_PASSWORD,
        )
        _, passenger_created = Passenger.objects.get_or_create(user=passenger_user)

        driver_user, _ = _ensure_user(
            'motorista@nextrouter.local',
            name='Carlos Silva',
            cpf=make_cpf('900000005'),
            password=DEV_PASSWORD,
        )
        _, driver_created = Driver.objects.get_or_create(user=driver_user)

        self.stdout.write(self.style.SUCCESS('Seed de homologação concluído com dados fictícios:'))
        self.stdout.write(
            f'  - Admin:      {admin_user.email} / {ADMIN_PASSWORD} '
            f'({"criado" if admin_created else "existente"})'
        )
        self.stdout.write(
            f'  - Empresa OK: {company_user.email} / {DEV_PASSWORD} '
            f'({supertransporte.trade_name}, id={supertransporte.id}, '
            f'{"criada" if st_created else "existente"}, pontos={garage_point.id},{dest_point.id})'
        )
        self.stdout.write(
            f'  - Pendente:   {pending_user.email} / {DEV_PASSWORD} '
            f'({pending_company.trade_name}, id={pending_company.id}, '
            f'{"criada" if pending_created else "existente"})'
        )
        self.stdout.write(
            f'  - Passageiro: {passenger_user.email} / {DEV_PASSWORD} '
            f'({"criado" if passenger_created else "existente"})'
        )
        self.stdout.write(
            f'  - Motorista:  {driver_user.email} / {DEV_PASSWORD} '
            f'({"criado" if driver_created else "existente"})'
        )
