"""Fixture exclusiva do smoke descartável; nunca importada por startup/seed de produção."""
# ruff: file-ignore[module-import-not-at-top-of-file]

import json
import os
from datetime import time, timedelta
from unittest.mock import patch

import django

if os.environ.get('NEXTROUTER_RUNTIME_SMOKE') != '1':
    raise RuntimeError('Fixture exige smoke fictício explícito.')
django.setup()

from django.core.files.base import ContentFile
from django.db import connection
from django.utils import timezone

from modules.accounts.models import User
from modules.organizations.models import (
    Company,
    CompanyMembership,
    Driver,
    OperationalPoint,
    Passenger,
    PassengerGroupMembership,
)
from modules.transport.models import (
    DailyResponse,
    PassengerServiceAuthorization,
    RecurringService,
    ResponsePolicy,
    Vehicle,
)
from modules.transport.services.automation import configure_automation
from modules.transport.services.calendar import generate_day
from modules.transport.services.execution import start_travel
from modules.transport.services.jobs import claim_snapshot_job, process_snapshot_job
from modules.transport.services.planning import close_day, publish_travel
from modules.uploads.models import Document

if connection.vendor != 'postgresql' or not connection.settings_dict['NAME'].startswith('nextrouter_smoke_'):
    raise RuntimeError('Fixture exige PostgreSQL novo do próprio smoke.')
if User.objects.exists():
    raise RuntimeError('Fixture só aceita banco novo e vazio do próprio smoke.')
now = timezone.now()
local = timezone.localtime(now)
password = 'SenhaFicticiaExclusivaDoSmoke!42'
users = [
    User.objects.create_user(
        email=f'{role}@example.invalid', password=password, name='Pessoa fictícia', cpf=f'9000000000{i}'
    )
    for i, role in enumerate(('company', 'driver', 'passenger'), 1)
]
company = Company.objects.create(user=users[0], cnpj='90000001000191', is_approved=True)
driver = Driver.objects.create(user=users[1])
passenger = Passenger.objects.create(user=users[2])
memberships = [
    CompanyMembership.objects.create(
        company=company,
        **{field: profile},
        status='active',
        requested_by=profile.user,
        created_at=now - timedelta(days=2),
        reviewed_at=now - timedelta(days=1),
        reviewed_by=company.user,
    )
    for field, profile in (('driver', driver), ('passenger', passenger))
]
points = [
    OperationalPoint.objects.create(
        company=company,
        created_by=company.user,
        name='Ponto fictício',
        street='RuaFicticiaNaoLogar',
        number='1',
        neighborhood='Fictício',
        city='Cidade fictícia',
        state='SC',
        cep='00000000',
        latitude=latitude,
        longitude=-48.8,
    )
    for latitude in (-26.3, -26.35, -26.4)
]
group = company.route_groups.create(name='Smoke fictício', destination=points[2])
participation = PassengerGroupMembership.objects.create(
    membership=memberships[1],
    route_group=group,
    transport_point=points[1],
    assigned_by=company.user,
    started_at=now - timedelta(hours=12),
)
vehicle = Vehicle.objects.create(company=company, plate='SMK1A23', capacity=2, garage_point=points[0])
service = RecurringService.objects.create(
    route_group=group,
    created_by=company.user,
    name='Ida fictícia',
    direction='outbound',
    weekdays=127,
    target_time=(local + timedelta(hours=1)).time(),
    valid_from=local.date(),
    planned_duration=timedelta(hours=2),
    turnaround_duration=timedelta(minutes=10),
    driver_membership=memberships[0],
    vehicle=vehicle,
    origin=points[0],
    destination=points[2],
)
PassengerServiceAuthorization.objects.create(
    participation=participation, service=service, direction='outbound', is_habitual=True
)
ResponsePolicy.objects.create(
    route_group=group,
    opens_days_before=1,
    opens_time=time(0),
    normal_days_before=0,
    normal_time=local.time().replace(microsecond=0),
)
day = generate_day(actor_id=company.user_id, group_id=group.pk, date=local.date())
DailyResponse.objects.create(
    eligibility=day.eligibilities.get(), outbound_service=service, answered_at=now - timedelta(minutes=1)
)
close_day(actor_id=company.user_id, day_id=day.pk)
job = claim_snapshot_job(company_id=company.pk, lease_duration=timedelta(seconds=60), max_attempts=1)


def route(coordinates, **kwargs):
    assert not connection.in_atomic_block
    return {
        'order': list(range(len(coordinates))),
        'geometry': {'type': 'LineString', 'coordinates': coordinates},
        'distance_meters': 1000,
        'duration_seconds': 300,
    }


with (
    patch('modules.transport.services.routing.optimize_coordinates', side_effect=route),
    patch('modules.transport.services.routing.route_coordinates', side_effect=route),
):
    assert process_snapshot_job(
        job_id=job.pk, claim_token=job.claim_token, max_attempts=1, retry_delay=timedelta(seconds=1)
    )
travel = day.travels.get()
publish_travel(actor_id=company.user_id, travel_id=travel.pk, expected_revision=travel.revision)
start_travel(actor_id=driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)
schedule = configure_automation(
    actor_id=company.user_id,
    group_id=group.pk,
    enabled=True,
    horizon_days=5,
    batch_size=1,
    interval_seconds=3600,
    next_run_at=now,
    expected_revision=0,
)
document = Document.objects.create(
    file=ContentFile(b'%PDF-1.4\n% apenas documento ficticio\n%%EOF\n', name='fixture.pdf')
)
driver.cnh = document
driver.save(update_fields=['cnh'])
print(
    json.dumps({
        'company_id': company.pk,
        'travel_id': travel.pk,
        'schedule_id': schedule.pk,
        'document_url': document.url,
        'document_name': document.file.name,
    })
)
