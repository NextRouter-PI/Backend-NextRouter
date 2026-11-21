"""Reset seguro do banco SQLite local e criação completa do cenário publicado."""

from datetime import time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction
from django.utils import timezone

from modules.accounts.models import User
from modules.organizations.models import Company, Driver, Passenger
from modules.organizations.services.groups import assign_passenger_group
from modules.organizations.services.memberships import approve_membership, request_membership
from modules.transport.models import RouteOptimizationJob, RouteSnapshot, Travel
from modules.transport.services.calendar import generate_day
from modules.transport.services.configuration import (
    authorize_services,
    configure_group,
    configure_point,
    configure_policy,
    configure_service,
    configure_vehicle,
)
from modules.transport.services.demand import answer_day
from modules.transport.services.governance import review_company
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
from modules.transport.services.planning import close_day, publish_travel
from modules.transport.services.routing import persist_stops
from shared.demo import make_cnpj, make_cpf

from .scenarios import ADMIN_PASSWORD, DEV_PASSWORD, TripScenario


def ensure_safe_local_sqlite() -> Path:
    """Garante que o reset só pode ocorrer em DEBUG=True no backend/dev.sqlite3."""
    if not settings.DEBUG:
        raise RuntimeError('Reset de banco recusado: permitido apenas com DEBUG=True.')
    db = settings.DATABASES['default']
    if db.get('ENGINE') != 'django.db.backends.sqlite3':
        raise RuntimeError('Reset de banco recusado: permitido apenas para SQLite local.')
    db_path = Path(db['NAME']).resolve()
    expected = (Path(settings.BASE_DIR) / 'dev.sqlite3').resolve()
    if db_path != expected:
        raise RuntimeError(f'Reset de banco recusado: caminho inesperado ({db_path}).')
    return db_path


def reset_local_sqlite(*, confirm_fictitious: bool) -> Path:
    """Apaga dev.sqlite3 (e WAL/SHM) e executa migrate do zero."""
    if not confirm_fictitious:
        raise RuntimeError('Reset de banco exige --confirm-fictitious.')
    db_path = ensure_safe_local_sqlite()
    connections.close_all()
    for suffix in ('', '-wal', '-shm', '-journal'):
        candidate = Path(f'{db_path}{suffix}')
        if candidate.exists():
            candidate.unlink()
    call_command('migrate', interactive=False, verbosity=0)
    with connections['default'].cursor() as cursor:
        cursor.execute('PRAGMA journal_mode=WAL;')
    return db_path


def _ensure_user(email: str, *, name: str, cpf: str, password: str, phone: str = '', is_superuser: bool = False):
    user = User.objects.filter(email=email).first()
    if user is not None:
        return user
    if is_superuser:
        return User.objects.create_superuser(email=email, password=password, name=name, cpf=cpf)
    user = User.objects.create_user(email=email, password=password, name=name, cpf=cpf)
    if phone:
        user.phone = phone
        user.save(update_fields=['phone'])
    return user


def _build_fallback_snapshot(travel: Travel, scenario: TripScenario) -> RouteSnapshot:
    """Completa o snapshot com a geometria de fallback do cenário quando OSRM não está disponível."""
    snapshot = travel.route_snapshots.order_by('-id').first()
    if snapshot is None:
        raise RuntimeError('Snapshot pendente não encontrado para a viagem.')
    coords = [[lng, lat] for lng, lat in scenario.fallback_geojson_coords]
    all_elig_ids = list(
        travel.participations.filter(status='allocated').order_by('pk').values_list('eligibility_id', flat=True)
    )
    rows = []
    if scenario.direction == 'return':
        rows.append({
            'point': snapshot.input_data['service']['common'],
            'eligibilities': all_elig_ids,
            'operation': 'board',
        })
    for participant in travel.participations.filter(status='allocated').select_related('eligibility').order_by('pk'):
        rows.append({
            'point': participant.eligibility.point_snapshot,
            'eligibilities': [participant.eligibility_id],
            'operation': 'board' if scenario.direction == 'outbound' else 'drop',
        })
    if scenario.direction == 'outbound':
        rows.append({
            'point': snapshot.input_data['service']['common'],
            'eligibilities': all_elig_ids,
            'operation': 'drop',
        })

    with transaction.atomic():
        snapshot.geometry = {'type': 'LineString', 'coordinates': coords}
        snapshot.distance_meters = 18400
        snapshot.duration_seconds = 1800
        snapshot.calculated_at = timezone.now()
        snapshot.state = 'ready'
        snapshot.planned_start = travel.planned_start
        snapshot.planned_end = travel.planned_end
        snapshot.full_clean()
        snapshot.save()
        persist_stops(snapshot, rows)
        RouteOptimizationJob.objects.filter(snapshot=snapshot).update(
            status='done', claim_token=None, claim_expires_at=None, error=''
        )
        travel.current_snapshot = snapshot
        travel.planning_status = 'ready'
        travel.save(update_fields=['current_snapshot', 'planning_status'])
    return snapshot


def prepare_scenario(scenario: TripScenario) -> dict:
    """Cria todo o domínio via services oficiais e deixa a viagem do cenário publicada e pronta."""
    moderator = _ensure_user(
        'admin@nextrouter.local',
        name='Administrador Local',
        cpf=make_cpf('900000001'),
        password=ADMIN_PASSWORD,
        is_superuser=True,
    )
    company_user = _ensure_user(
        'empresa@nextrouter.local',
        name='SuperTransporte Gestor',
        cpf=make_cpf('900000002'),
        password=DEV_PASSWORD,
        phone='47999990001',
    )
    company, _ = Company.objects.get_or_create(
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
        },
    )
    if not company.is_approved:
        review_company(actor_id=moderator.pk, company_id=company.pk, approve=True)

    driver_user = _ensure_user(
        'motorista@nextrouter.local',
        name='Carlos Silva',
        cpf=make_cpf('900000005'),
        password=DEV_PASSWORD,
        phone='47999990005',
    )
    driver, _ = Driver.objects.get_or_create(user=driver_user)
    driver_membership = company.memberships.filter(driver=driver, status='active').first()
    if driver_membership is None:
        driver_membership = request_membership(actor_id=driver_user.pk, company_id=company.pk, driver_id=driver.pk)
        driver_membership = approve_membership(actor_id=company_user.pk, membership_id=driver_membership.pk)

    existing_garage = company.operational_points.filter(name=scenario.garage.name).first()
    garage = configure_point(
        actor_id=company_user.pk,
        company_id=company.pk,
        point_id=existing_garage.pk if existing_garage else None,
        name=scenario.garage.name,
        point_type=scenario.garage.point_type,
        street=scenario.garage.street,
        number=scenario.garage.number,
        neighborhood=scenario.garage.neighborhood,
        city=scenario.garage.city,
        state=scenario.garage.state,
        cep=scenario.garage.cep,
        latitude=scenario.garage.latitude,
        longitude=scenario.garage.longitude,
    )
    existing_dest = company.operational_points.filter(name=scenario.destination.name).first()
    destination = configure_point(
        actor_id=company_user.pk,
        company_id=company.pk,
        point_id=existing_dest.pk if existing_dest else None,
        name=scenario.destination.name,
        point_type=scenario.destination.point_type,
        street=scenario.destination.street,
        number=scenario.destination.number,
        neighborhood=scenario.destination.neighborhood,
        city=scenario.destination.city,
        state=scenario.destination.state,
        cep=scenario.destination.cep,
        latitude=scenario.destination.latitude,
        longitude=scenario.destination.longitude,
    )
    existing_vehicle = company.fleet.filter(plate='SIM1A23').first()
    vehicle = configure_vehicle(
        actor_id=company_user.pk,
        company_id=company.pk,
        vehicle_id=existing_vehicle.pk if existing_vehicle else None,
        plate='SIM1A23',
        capacity=15,
        garage_point_id=garage.pk,
    )
    existing_group = company.route_groups.filter(name='IFC Araquari — Simulação').first()
    group = configure_group(
        actor_id=company_user.pk,
        company_id=company.pk,
        group_id=existing_group.pk if existing_group else None,
        name='IFC Araquari — Simulação',
        destination_id=destination.pk,
    )
    # Janela normal aberta agora (abriu ontem, fecha amanhã) para permitir resposta via answer_day.
    configure_policy(
        actor_id=company_user.pk,
        group_id=group.pk,
        opens_days_before=2,
        opens_time=time(0, 0),
        normal_days_before=0,
        normal_time=time(23, 59),
        extension_days_before=None,
        extension_time=None,
    )

    today = timezone.localdate()
    all_weekdays = 0b1111111
    service = configure_service(
        actor_id=company_user.pk,
        group_id=group.pk,
        name=scenario.service_name,
        direction=scenario.direction,
        weekdays=all_weekdays,
        target_time=time(scenario.target_hour, scenario.target_minute),
        planned_duration=timedelta(minutes=60),
        turnaround_duration=timedelta(minutes=10),
        driver_membership_id=driver_membership.pk,
        vehicle_id=vehicle.pk,
        valid_from=today - timedelta(days=1),
        valid_until=today + timedelta(days=30),
    )

    passenger_records = []
    for spec in scenario.passengers:
        p_user = _ensure_user(
            spec.email,
            name=spec.name,
            cpf=make_cpf(spec.cpf_seed),
            password=DEV_PASSWORD,
            phone=spec.phone,
        )
        passenger, _ = Passenger.objects.get_or_create(user=p_user)
        membership = company.memberships.filter(passenger=passenger, status='active').first()
        if membership is None:
            membership = request_membership(actor_id=p_user.pk, company_id=company.pk, passenger_id=passenger.pk)
            membership = approve_membership(actor_id=company_user.pk, membership_id=membership.pk)
        p_point = configure_point(
            actor_id=company_user.pk,
            company_id=company.pk,
            name=spec.point.name,
            point_type=spec.point.point_type,
            street=spec.point.street,
            number=spec.point.number,
            neighborhood=spec.point.neighborhood,
            city=spec.point.city,
            state=spec.point.state,
            cep=spec.point.cep,
            latitude=spec.point.latitude,
            longitude=spec.point.longitude,
        )
        gm = assign_passenger_group(
            actor_id=company_user.pk,
            membership_id=membership.pk,
            route_group_id=group.pk,
            transport_point_id=p_point.pk,
        )
        authorize_services(
            actor_id=company_user.pk,
            group_membership_id=gm.pk,
            service_ids=[service.pk],
            habitual_outbound_id=service.pk if scenario.direction == 'outbound' else None,
        )
        passenger_records.append((p_user, passenger))

    day = generate_day(actor_id=company_user.pk, group_id=group.pk, date=today)
    for p_user, passenger in passenger_records:
        elig = day.eligibilities.get(passenger=passenger)
        answer_day(
            actor_id=p_user.pk,
            eligibility_id=elig.pk,
            outbound_service_id=service.pk if scenario.direction == 'outbound' else None,
            return_service_id=service.pk if scenario.direction == 'return' else None,
            expected_revision=0,
        )

    # Fecha a janela no passado para consolidar imediatamente via close_day.
    day.normal_deadline = timezone.now() - timedelta(minutes=1)
    day.save(update_fields=['normal_deadline'])
    close_day(actor_id=company_user.pk, day_id=day.pk)

    travel = day.travels.get(service=service)
    used_osrm = False
    if getattr(settings, 'OSRM_URL', ''):
        job = claim_snapshot_job(company_id=company.pk, lease_duration=timedelta(seconds=60), max_attempts=2)
        if job is not None:
            used_osrm = bool(
                process_snapshot_job(
                    job_id=job.pk,
                    claim_token=job.claim_token,
                    max_attempts=2,
                    retry_delay=timedelta(seconds=1),
                )
            )
    travel.refresh_from_db()
    if travel.planning_status != 'ready' or travel.current_snapshot is None:
        _build_fallback_snapshot(travel, scenario)
        travel.refresh_from_db()
        used_osrm = False

    publish_travel(actor_id=company_user.pk, travel_id=travel.pk, expected_revision=travel.revision)
    travel.refresh_from_db()

    snapshot = travel.current_snapshot
    stops = list(
        snapshot.stops.prefetch_related('participants__participation__eligibility__passenger__user').order_by(
            'position'
        )
    )
    stop_plan = [
        {
            'id': stop.pk,
            'position': stop.position,
            'name': stop.point_snapshot.get('name', f'Parada #{stop.position}'),
            'latitude': stop.point_snapshot.get('latitude'),
            'longitude': stop.point_snapshot.get('longitude'),
            'participants': [
                {
                    'participation_id': sp.participation_id,
                    'operation': sp.operation,
                    'passenger_name': sp.participation.eligibility.passenger.user.name,
                }
                for sp in stop.participants.all()
            ],
        }
        for stop in stops
    ]

    return {
        'scenario': scenario.key,
        'label': scenario.label,
        'travel_id': travel.pk,
        'travel_revision': travel.revision,
        'used_osrm': used_osrm,
        'geometry_coords': snapshot.geometry['coordinates'],
        'stops': stop_plan,
        'driver_email': driver_user.email,
        'driver_password': DEV_PASSWORD,
        'passenger_email': scenario.passengers[0].email,
        'passenger_password': DEV_PASSWORD,
        'company_email': company_user.email,
        'company_password': DEV_PASSWORD,
    }
