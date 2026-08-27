import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from authenticator.models import Company, CompanyRouteGroup, Driver, Passenger, User
from router.models import CompanyRouteSchedule, Path, Travel, Vehicle

CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
CNPJ_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def _check_digit(digits, start_weight):
    weights = range(start_weight, 1, -1)
    total = sum(d * w for d, w in zip(digits, weights, strict=True))
    remainder = (total * 10) % 11
    return 0 if remainder == 10 else remainder


def make_cpf(base9: str) -> str:
    digits = [int(c) for c in base9]
    d1 = _check_digit(digits, 10)
    d2 = _check_digit([*digits, d1], 11)
    return f'{base9}{d1}{d2}'


def make_cnpj(base12: str) -> str:
    digits = [int(c) for c in base12]
    total_1 = sum(d * w for d, w in zip(digits, CNPJ_WEIGHTS_1, strict=True))
    remainder_1 = total_1 % 11
    d1 = 0 if remainder_1 < 2 else 11 - remainder_1

    total_2 = sum(d * w for d, w in zip([*digits, d1], CNPJ_WEIGHTS_2, strict=True))
    remainder_2 = total_2 % 11
    d2 = 0 if remainder_2 < 2 else 11 - remainder_2

    return f'{base12}{d1}{d2}'


COMPANIES = [
    {
        'slug': 'transnorte',
        'trade_name': 'TransNorte Transportes',
        'legal_name': 'TransNorte Transportes Ltda',
        'cnpj': make_cnpj('111222330001'),
        'email': 'contato@transnorte.com.br',
        'cpf': make_cpf('100200300'),
        'city': 'Blumenau',
        'state': 'SC',
        'cep': '89010-000',
        'street': 'Rua XV de Novembro',
        'number': '500',
        'neighborhood': 'Centro',
        'route_groups': [
            {
                'name': 'Rota Centro-Garcia',
                'common_cep': '89010-000',
                'schedules': [('06:30', '18:00')],
                'drivers': [
                    {'name': 'Marcos Antunes', 'email': 'marcos.antunes@transnorte.com.br', 'cpf_base': '200300400'},
                    {'name': 'Juliana Bittencourt', 'email': 'juliana.bittencourt@transnorte.com.br', 'cpf_base': '200300500'},
                ],
                'vehicles': [
                    {'plate': 'BLU1A23', 'model': 'Mercedes-Benz Sprinter', 'year': 2021, 'capacity': 16, 'color': 'Branco'},
                    {'plate': 'BLU2B34', 'model': 'Volkswagen Crafter', 'year': 2022, 'capacity': 18, 'color': 'Prata'},
                ],
                'passengers': [
                    {'name': 'Ana Beatriz Souza', 'email': 'ana.souza@example.com', 'cpf_base': '300400500'},
                    {'name': 'Carlos Eduardo Lima', 'email': 'carlos.lima@example.com', 'cpf_base': '300400600'},
                    {'name': 'Fernanda Costa', 'email': 'fernanda.costa@example.com', 'cpf_base': '300400700'},
                    {'name': 'Gustavo Ramos', 'email': 'gustavo.ramos@example.com', 'cpf_base': '300400800'},
                ],
            },
        ],
    },
    {
        'slug': 'rotafacil',
        'trade_name': 'Rota Fácil Fretamento',
        'legal_name': 'Rota Fácil Fretamento Ltda',
        'cnpj': make_cnpj('444555660001'),
        'email': 'contato@rotafacil.com.br',
        'cpf': make_cpf('400500600'),
        'city': 'Rio do Sul',
        'state': 'SC',
        'cep': '89160-000',
        'street': 'Rua Duque de Caxias',
        'number': '120',
        'neighborhood': 'Centro',
        'route_groups': [
            {
                'name': 'Rota Centro-Laranjeiras',
                'common_cep': '89160-000',
                'schedules': [('07:00', '17:30')],
                'drivers': [
                    {'name': 'Rodrigo Peixoto', 'email': 'rodrigo.peixoto@rotafacil.com.br', 'cpf_base': '500600700'},
                ],
                'vehicles': [
                    {'plate': 'RSU3C45', 'model': 'Iveco Daily', 'year': 2020, 'capacity': 14, 'color': 'Azul'},
                ],
                'passengers': [
                    {'name': 'Larissa Nogueira', 'email': 'larissa.nogueira@example.com', 'cpf_base': '600700800'},
                    {'name': 'Pedro Henrique Alves', 'email': 'pedro.alves@example.com', 'cpf_base': '600700900'},
                    {'name': 'Sabrina Teixeira', 'email': 'sabrina.teixeira@example.com', 'cpf_base': '600701000'},
                ],
            },
        ],
    },
    {
        'slug': 'valeexpresso',
        'trade_name': 'Vale Expresso Transportes',
        'legal_name': 'Vale Expresso Transportes Ltda',
        'cnpj': make_cnpj('777888990001'),
        'email': 'contato@valeexpresso.com.br',
        'cpf': make_cpf('700800900'),
        'city': 'Camboriú',
        'state': 'SC',
        'cep': '88340-000',
        'street': 'Avenida Santa Catarina',
        'number': '2200',
        'neighborhood': 'Centro',
        'route_groups': [
            {
                'name': 'Rota Praia-Centro',
                'common_cep': '88340-000',
                'schedules': [('06:00', '19:00')],
                'drivers': [
                    {'name': 'Eduardo Martins', 'email': 'eduardo.martins@valeexpresso.com.br', 'cpf_base': '800900100'},
                    {'name': 'Camila Duarte', 'email': 'camila.duarte@valeexpresso.com.br', 'cpf_base': '800900200'},
                ],
                'vehicles': [
                    {'plate': 'CBU4D56', 'model': 'Renault Master', 'year': 2023, 'capacity': 15, 'color': 'Cinza'},
                    {'plate': 'CBU5E67', 'model': 'Fiat Ducato', 'year': 2021, 'capacity': 16, 'color': 'Branco'},
                ],
                'passengers': [
                    {'name': 'Bruna Fagundes', 'email': 'bruna.fagundes@example.com', 'cpf_base': '900100200'},
                    {'name': 'Diego Correia', 'email': 'diego.correia@example.com', 'cpf_base': '900100300'},
                    {'name': 'Isabela Franco', 'email': 'isabela.franco@example.com', 'cpf_base': '900100400'},
                    {'name': 'Lucas Andrade', 'email': 'lucas.andrade@example.com', 'cpf_base': '900100500'},
                    {'name': 'Mariana Vieira', 'email': 'mariana.vieira@example.com', 'cpf_base': '900100600'},
                ],
            },
        ],
    },
]

DEMO_PASSWORD = 'Demo@1234'


class Command(BaseCommand):
    help = (
        'Popula o banco com dados de demonstração (empresas, motoristas, passageiros, '
        'veículos e rotas) para o ambiente publicado. É idempotente (get_or_create), '
        'então pode ser executado mais de uma vez sem duplicar registros. Só roda de fato '
        "quando a variável de ambiente SEED_DEMO_DATA='true' está definida, para não "
        'acontecer sem querer em todo deploy.'
    )

    def handle(self, *args, **options):
        if os.getenv('SEED_DEMO_DATA', 'false').lower() != 'true':
            self.stdout.write("SEED_DEMO_DATA não está 'true', pulando população de dados de demonstração.")
            return

        with transaction.atomic():
            for company_data in COMPANIES:
                self._create_company(company_data)

        self.stdout.write(self.style.SUCCESS('Dados de demonstração populados com sucesso.'))
        self.stdout.write(f'Todos os usuários de demonstração usam a senha: {DEMO_PASSWORD}')

    def _create_user(self, *, name, email, cpf, city, state, cep, street, number, neighborhood):
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'name': name,
                'cpf': cpf,
                'city': city,
                'state': state,
                'cep': cep,
                'street': street,
                'number': number,
                'neighborhood': neighborhood,
                'is_active': True,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save(update_fields=['password'])
            self.stdout.write(f'  Usuário criado: {email}')
        return user

    def _create_company(self, data):
        user = self._create_user(
            name=data['trade_name'],
            email=data['email'],
            cpf=data['cpf'],
            city=data['city'],
            state=data['state'],
            cep=data['cep'],
            street=data['street'],
            number=data['number'],
            neighborhood=data['neighborhood'],
        )

        company, created = Company.objects.get_or_create(
            cnpj=data['cnpj'],
            defaults={
                'user': user,
                'trade_name': data['trade_name'],
                'legal_name': data['legal_name'],
                'state_registration': '000000000',
                'contact_email': data['email'],
                'is_approved': True,
                'city': data['city'],
                'state': data['state'],
                'cep': data['cep'],
                'street': data['street'],
                'number': data['number'],
                'neighborhood': data['neighborhood'],
            },
        )
        self.stdout.write(f"Empresa: {data['trade_name']} ({'criada' if created else 'já existia'})")

        for group_data in data['route_groups']:
            self._create_route_group(company, data, group_data)

    def _create_route_group(self, company, company_data, group_data):
        route_group, _ = CompanyRouteGroup.objects.get_or_create(
            company=company,
            name=group_data['name'],
            defaults={'common_cep': group_data['common_cep']},
        )

        for go_hour, return_hour in group_data['schedules']:
            CompanyRouteSchedule.objects.get_or_create(
                route_group=route_group,
                go_hour=go_hour,
                return_hour=return_hour,
            )

        drivers = []
        for driver_data in group_data['drivers']:
            user = self._create_user(
                name=driver_data['name'],
                email=driver_data['email'],
                cpf=make_cpf(driver_data['cpf_base']),
                city=company_data['city'],
                state=company_data['state'],
                cep=company_data['cep'],
                street=company_data['street'],
                number=str(int(company_data['number']) + 10),
                neighborhood=company_data['neighborhood'],
            )
            driver, _ = Driver.objects.get_or_create(
                user=user,
                defaults={'route_group': route_group, 'is_approved': True},
            )
            if driver.route_group_id != route_group.id or not driver.is_approved:
                driver.route_group = route_group
                driver.is_approved = True
                driver.save(update_fields=['route_group', 'is_approved'])
            drivers.append(driver)

        for index, vehicle_data in enumerate(group_data['vehicles']):
            Vehicle.objects.get_or_create(
                plate=vehicle_data['plate'],
                defaults={
                    'route_group': route_group,
                    'driver': drivers[index] if index < len(drivers) else None,
                    'model': vehicle_data['model'],
                    'year': vehicle_data['year'],
                    'capacity': vehicle_data['capacity'],
                    'color': vehicle_data['color'],
                    'garage_cep': company_data['cep'],
                    'status': Vehicle.Status.ACTIVE,
                    'features': ['Ar-condicionado', 'Cinto de segurança'],
                },
            )

        for passenger_data in group_data['passengers']:
            user = self._create_user(
                name=passenger_data['name'],
                email=passenger_data['email'],
                cpf=make_cpf(passenger_data['cpf_base']),
                city=company_data['city'],
                state=company_data['state'],
                cep=company_data['cep'],
                street=company_data['street'],
                number=str(int(company_data['number']) + 20),
                neighborhood=company_data['neighborhood'],
            )
            Passenger.objects.get_or_create(
                user=user,
                defaults={'route_group': route_group, 'is_approved': True},
            )

        self._create_travels(company, route_group, drivers)

    def _create_travels(self, company, route_group, drivers):
        if not drivers:
            return

        # get_or_create abaixo usa started_at, que é calculado a partir de timezone.now() — se
        # já existem viagens para essa empresa, não recalcula, senão cada execução do comando
        # geraria um novo now() (segundos diferentes) e duplicaria as viagens a cada deploy.
        if Travel.objects.filter(company=company).exists():
            return

        path = Path.objects.filter(route_group=route_group).order_by('id').first()
        if not path:
            path = Path.objects.create(route_group=route_group, name='Trajeto automático', points=[])

        now = timezone.now()
        travel_plans = [
            (drivers[0], Travel.Status.FINISHED, now - timedelta(days=1), now - timedelta(days=1) + timedelta(hours=1)),
            (drivers[0], Travel.Status.SCHEDULED, now + timedelta(days=1), None),
        ]
        if len(drivers) > 1:
            travel_plans.append((drivers[1], Travel.Status.IN_PROGRESS, now - timedelta(minutes=20), None))

        for driver, status, started_at, finished_at in travel_plans:
            Travel.objects.get_or_create(
                company=company,
                driver=driver,
                path=path,
                status=status,
                started_at=started_at,
                defaults={'finished_at': finished_at},
            )
