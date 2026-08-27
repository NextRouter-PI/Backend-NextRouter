import datetime
import random

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from authenticator.models import Company, CompanyRouteGroup, Driver, Passenger, User
from router.models import CompanyRouteSchedule, ConfirmPassengerRoute, LostItem, Path, Travel, Vehicle

DEFAULT_PASSWORD = 'senha123'

FALLBACK_STREETS = [
    'Rua das Palmeiras', 'Rua Barão do Rio Branco', 'Rua Blumenau',
    'Rua Otto Boehm', 'Rua Iririu', 'Rua Anita Garibaldi', 'Rua Ottokar Doerffel',
]


def gen_cpf(base: str) -> str:
    base = base.rjust(9, '0')[:9]
    digits = [int(d) for d in base]

    total = sum(d * (10 - i) for i, d in enumerate(digits))
    d1 = (total * 10) % 11
    d1 = 0 if d1 == 10 else d1
    digits.append(d1)

    total = sum(d * (11 - i) for i, d in enumerate(digits))
    d2 = (total * 10) % 11
    d2 = 0 if d2 == 10 else d2
    digits.append(d2)

    return ''.join(str(d) for d in digits)


def gen_cnpj(base: str) -> str:
    base = base.rjust(12, '0')[:12]
    digits = [int(d) for d in base]

    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(d * w for d, w in zip(digits, weights1))
    remainder = total % 11
    d1 = 0 if remainder < 2 else 11 - remainder
    digits.append(d1)

    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(d * w for d, w in zip(digits, weights2))
    remainder = total % 11
    d2 = 0 if remainder < 2 else 11 - remainder
    digits.append(d2)

    return ''.join(str(d) for d in digits)


COMPANIES = [
    {
        'trade_name': 'Viação Araquari',
        'legal_name': 'Viação Araquari Transportes LTDA',
        'cnpj_base': '11222333000',
        'state_registration': '110022330',
        'contact_email': 'contato@viacaoaraquari.com.br',
        'contact_phone': '47999990001',
        'email': 'empresa.araquari@nextrouter.com',
        'name': 'Viação Araquari',
        'cep': '89225000',
        'cpf_base': '10020030040',
        'route_groups': [
            {'name': 'Centro - Joinville', 'common_cep': '89201000'},
            {'name': 'América - Joinville', 'common_cep': '89204000'},
        ],
    },
    {
        'trade_name': 'TransNorte Fretamentos',
        'legal_name': 'TransNorte Fretamentos e Turismo LTDA',
        'cnpj_base': '22333444000',
        'state_registration': '220033440',
        'contact_email': 'contato@transnorte.com.br',
        'contact_phone': '47999990002',
        'email': 'empresa.transnorte@nextrouter.com',
        'name': 'TransNorte Fretamentos',
        'cep': '89218000',
        'cpf_base': '20030040050',
        'route_groups': [
            {'name': 'Bucarein - Joinville', 'common_cep': '89202000'},
        ],
    },
]

DRIVER_NAMES = [
    'Roberto Carlos Souza', 'Eduardo Lima Santos', 'Marcos Vinícius Alves',
    'José Antônio Ferreira', 'Paulo Henrique Costa',
]

PASSENGER_NAMES = [
    'Ana Beatriz Silva', 'João Pedro Oliveira', 'Mariana Costa Rocha',
    'Lucas Mendes Araújo', 'Fernanda Lima Souza', 'Rafael Souza Martins',
    'Juliana Rocha Pereira', 'Thiago Martins Cardoso', 'Camila Duarte Ramos',
    'Bruno Fernandes Teixeira',
]

LOST_ITEM_DESCRIPTIONS = [
    'Garrafa de água azul', 'Caderno universitário', 'Fone de ouvido branco',
    'Boné preto', 'Carregador de celular',
]


class Command(BaseCommand):
    help = 'Popula o banco de dados com dados de exemplo (empresas, motoristas, passageiros, rotas, veículos, viagens).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Remove os dados de exemplo criados anteriormente por este comando antes de recriar.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self._reset()

        if not User.objects.filter(email='admin@nextrouter.com').exists():
            User.objects.create_superuser(
                email='admin@nextrouter.com',
                password=DEFAULT_PASSWORD,
                name='Administrador NextRouter',
                cpf=gen_cpf('00011122'),
            )
            self.stdout.write(self.style.SUCCESS('Superusuário criado: admin@nextrouter.com'))
        else:
            self.stdout.write('Superusuário já existe, pulando.')

        driver_pool = iter(DRIVER_NAMES)
        passenger_pool = iter(PASSENGER_NAMES)
        all_travels = []

        for company_index, company_data in enumerate(COMPANIES, start=1):
            company = self._create_company(company_index, company_data)
            route_groups = self._create_route_groups(company, company_data['route_groups'])

            for group_index, group in enumerate(route_groups, start=1):
                driver = self._create_driver(company_index, group_index, group, driver_pool)
                vehicle = self._create_vehicle(company_index, group_index, group, driver)
                self._create_schedules(group)
                path = self._create_path(group)
                passengers = self._create_passengers(company_index, group_index, group, passenger_pool, count=3)

                travel = self._create_travel(company, driver, path)
                all_travels.append((travel, passengers))

        for travel, passengers in all_travels:
            self._create_confirmations(travel, passengers)

        self._create_lost_items(all_travels)

        self.stdout.write(self.style.SUCCESS('Banco de dados populado com sucesso.'))
        self.stdout.write('Senha padrão de todos os usuários criados: ' + DEFAULT_PASSWORD)

    def _reset(self):
        LostItem.objects.all().delete()
        ConfirmPassengerRoute.objects.all().delete()
        Travel.objects.all().delete()
        Vehicle.objects.all().delete()
        Path.objects.all().delete()
        CompanyRouteSchedule.objects.all().delete()
        Driver.objects.filter(user__email__endswith='@nextrouter.com').delete()
        Passenger.objects.filter(user__email__endswith='@nextrouter.com').delete()
        CompanyRouteGroup.objects.all().delete()
        Company.objects.filter(user__email__endswith='@nextrouter.com').delete()
        User.objects.filter(email__endswith='@nextrouter.com', is_superuser=False).delete()
        self.stdout.write('Dados de exemplo anteriores removidos.')

    def _create_company(self, index, data):
        user, created = User.objects.get_or_create(
            email=data['email'],
            defaults={
                'name': data['name'],
                'cpf': gen_cpf(data['cpf_base']),
                'cep': data['cep'],
                'street': 'Rua XV de Novembro',
                'number': str(100 + index),
                'neighborhood': 'Centro',
                'city': 'Joinville',
                'state': 'SC',
                'phone': '4799999' + str(1000 + index),
                'birthday': datetime.date(1985, 1, index),
            },
        )
        if created:
            user.set_password(DEFAULT_PASSWORD)
            user.save(update_fields=['password'])

        company, _ = Company.objects.get_or_create(
            user=user,
            defaults={
                'trade_name': data['trade_name'],
                'legal_name': data['legal_name'],
                'cnpj': gen_cnpj(data['cnpj_base']),
                'state_registration': data['state_registration'],
                'contact_email': data['contact_email'],
                'contact_phone': data['contact_phone'],
                'cep': data['cep'],
                'street': 'Rua XV de Novembro',
                'number': str(100 + index),
                'neighborhood': 'Centro',
                'city': 'Joinville',
                'state': 'SC',
                'is_approved': True,
            },
        )
        self.stdout.write(f'Empresa criada: {company.trade_name} ({user.email})')
        return company

    def _create_route_groups(self, company, groups_data):
        groups = []
        for group_data in groups_data:
            group, _ = CompanyRouteGroup.objects.get_or_create(
                company=company,
                name=group_data['name'],
                defaults={'common_cep': group_data['common_cep']},
            )
            groups.append(group)
        return groups

    def _create_driver(self, company_index, group_index, route_group, driver_pool):
        name = next(driver_pool, f'Motorista {company_index}-{group_index}')
        email = f'motorista{company_index}{group_index}@nextrouter.com'
        base_cpf = f'{company_index}{group_index}0300400'

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'name': name,
                'cpf': gen_cpf(base_cpf),
                'cep': route_group.common_cep,
                'street': FALLBACK_STREETS[(company_index * 10 + group_index) % len(FALLBACK_STREETS)],
                'number': str(100 + company_index * 10 + group_index),
                'neighborhood': route_group.name.split(' - ')[0],
                'city': 'Joinville',
                'state': 'SC',
                'phone': '4798888' + str(1000 + company_index * 10 + group_index),
                'birthday': datetime.date(1988, 3, 10),
            },
        )
        if created:
            user.set_password(DEFAULT_PASSWORD)
            user.save(update_fields=['password'])

        driver, _ = Driver.objects.get_or_create(
            user=user,
            defaults={'route_group': route_group, 'is_approved': True},
        )
        if driver.route_group_id != route_group.id or not driver.is_approved:
            driver.route_group = route_group
            driver.is_approved = True
            driver.save(update_fields=['route_group', 'is_approved'])

        self.stdout.write(f'  Motorista criado: {name} ({email})')
        return driver

    def _create_vehicle(self, company_index, group_index, route_group, driver):
        plate = f'NXT{company_index}{group_index}{random.randint(10, 99)}'
        vehicle, _ = Vehicle.objects.get_or_create(
            route_group=route_group,
            plate=plate,
            defaults={
                'driver': driver,
                'garage_cep': route_group.common_cep,
                'model': 'Mercedes Sprinter',
                'year': 2022,
                'capacity': 18,
                'status': Vehicle.Status.ACTIVE,
            },
        )
        self.stdout.write(f'  Veículo criado: {plate}')
        return vehicle

    def _create_schedules(self, route_group):
        pairs = [(datetime.time(7, 0), datetime.time(12, 0)), (datetime.time(13, 0), datetime.time(18, 0))]
        for go_hour, return_hour in pairs:
            CompanyRouteSchedule.objects.get_or_create(
                route_group=route_group,
                go_hour=go_hour,
                return_hour=return_hour,
            )

    def _create_path(self, route_group):
        path, _ = Path.objects.get_or_create(
            route_group=route_group,
            name=f'Trajeto {route_group.name}',
            defaults={
                'points': [
                    {'order': 1, 'label': route_group.name, 'lat': -26.3, 'lng': -48.8},
                    {'order': 2, 'label': 'IFC - Araquari', 'lat': -26.37, 'lng': -48.72},
                ],
            },
        )
        return path

    def _create_passengers(self, company_index, group_index, route_group, passenger_pool, count):
        passengers = []
        for i in range(1, count + 1):
            name = next(passenger_pool, f'Passageiro {company_index}-{group_index}-{i}')
            email = f'passageiro{company_index}{group_index}{i}@nextrouter.com'
            base_cpf = f'{company_index}{group_index}{i}040050'

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'name': name,
                    'cpf': gen_cpf(base_cpf),
                    'cep': route_group.common_cep,
                    'street': FALLBACK_STREETS[(company_index * 100 + group_index * 10 + i) % len(FALLBACK_STREETS)],
                    'number': str(100 + company_index * 100 + group_index * 10 + i),
                    'neighborhood': route_group.name.split(' - ')[0],
                    'city': 'Joinville',
                    'state': 'SC',
                    'phone': '4797777' + str(1000 + company_index * 100 + group_index * 10 + i),
                    'birthday': datetime.date(2000, (i % 12) + 1, 15),
                },
            )
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save(update_fields=['password'])

            passenger, _ = Passenger.objects.get_or_create(
                user=user,
                defaults={'route_group': route_group, 'is_approved': True},
            )
            if passenger.route_group_id != route_group.id or not passenger.is_approved:
                passenger.route_group = route_group
                passenger.is_approved = True
                passenger.save(update_fields=['route_group', 'is_approved'])

            passengers.append(passenger)
        self.stdout.write(f'  {count} passageiros criados para o grupo {route_group.name}')
        return passengers

    def _create_travel(self, company, driver, path):
        now = timezone.now()
        travel, _ = Travel.objects.get_or_create(
            company=company,
            driver=driver,
            path=path,
            started_at=now.replace(hour=7, minute=0, second=0, microsecond=0),
            defaults={'finished_at': now.replace(hour=7, minute=45, second=0, microsecond=0)},
        )
        return travel

    def _create_confirmations(self, travel, passengers):
        for passenger in passengers:
            ConfirmPassengerRoute.objects.get_or_create(
                travel=travel,
                user=passenger.user,
                defaults={'confirm': random.choice([True, True, False])},
            )

    def _create_lost_items(self, all_travels):
        statuses = [LostItem.Status.REPORTED, LostItem.Status.FOUND, LostItem.Status.RETURNED]
        item_index = 0
        for travel, passengers in all_travels:
            if not passengers:
                continue
            passenger = passengers[0]
            description = LOST_ITEM_DESCRIPTIONS[item_index % len(LOST_ITEM_DESCRIPTIONS)]
            LostItem.objects.get_or_create(
                travel=travel,
                user=passenger.user,
                item_description=description,
                defaults={'status': statuses[item_index % len(statuses)]},
            )
            item_index += 1
