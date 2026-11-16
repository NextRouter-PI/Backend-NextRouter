from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from modules.transport.models import RecurringService, RouteSnapshot
from modules.transport.services.calendar import generate_horizon
from modules.transport.services.configuration import (
    authorize_services,
    configure_group,
    configure_point,
    configure_service,
    configure_stops,
    configure_vehicle,
)
from modules.transport.services.planning import assign_vehicle
from tests.helpers import create_operational_point

from .service_helpers import ServiceTestCase


class ConfigurationServiceTests(ServiceTestCase):
    def test_duration_constraints_reject_bulk_updates_but_allow_incomplete_drafts(self):
        for values in ({'planned_duration': timedelta()}, {'turnaround_duration': timedelta(seconds=-1)}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RecurringService.objects.filter(pk=self.outbound.pk).update(**values)
        RecurringService.objects.filter(pk=self.outbound.pk).update(planned_duration=None, turnaround_duration=None)
        self.outbound.refresh_from_db()
        self.outbound.full_clean()

    def test_foreign_objects_and_protected_configuration_fields_are_rejected(self):
        foreign = create_operational_point(self.other)
        self.assert_domain(
            'not_found',
            configure_group,
            actor_id=self.company.user_id,
            company_id=self.company.pk,
            name='Grupo fictício',
            destination_id=foreign.pk,
        )
        self.assert_domain(
            'protected_field',
            configure_service,
            actor_id=self.company.user_id,
            group_id=self.group.pk,
            service_id=self.outbound.pk,
            created_by_id=self.other.user_id,
        )
        with self.assertRaises(ValidationError):
            configure_service(
                actor_id=self.company.user_id, group_id=self.group.pk, service_id=self.outbound.pk, origin_id=foreign.pk
            )

    def test_company_configures_points_and_fleet_without_external_geocoding(self):
        point = configure_point(
            actor_id=self.company.user_id,
            company_id=self.company.pk,
            name='Garagem fictícia',
            street='Rua Fictícia',
            number='25',
            neighborhood='Centro',
            city='Blumenau',
            state='SC',
            cep='89010-000',
            latitude=-26.3,
            longitude=-48.8,
        )
        vehicle = configure_vehicle(
            actor_id=self.company.user_id,
            company_id=self.company.pk,
            plate='DEF2E34',
            capacity=5,
            garage_point_id=point.pk,
        )
        self.assertEqual(vehicle.company_id, self.company.pk)
        self.assertEqual(vehicle.garage_point_id, point.pk)
        self.assertNotIn('route_group', {field.name for field in vehicle._meta.fields})

    def test_service_authorization_is_scoped_and_habitual_only_for_outbound(self):
        self.assert_domain(
            'invalid_habitual',
            authorize_services,
            actor_id=self.company.user_id,
            group_membership_id=self.group_member.pk,
            service_ids=[self.returning.pk],
            habitual_outbound_id=self.returning.pk,
        )
        self.assert_domain(
            'invalid_services',
            authorize_services,
            actor_id=self.company.user_id,
            group_membership_id=self.group_member.pk,
            service_ids=[999999],
        )
        result = authorize_services(
            actor_id=self.company.user_id,
            group_membership_id=self.group_member.pk,
            service_ids=[self.outbound.pk, self.returning.pk],
            habitual_outbound_id=self.outbound.pk,
        )
        self.assertEqual(len(result), 2)

    def test_horizon_and_batch_are_explicit_and_idempotent(self):
        days = generate_horizon(
            actor_id=self.company.user_id, group_id=self.group.pk, start_date=self.date, horizon_days=7, batch_size=2
        )
        repeated = generate_horizon(
            actor_id=self.company.user_id, group_id=self.group.pk, start_date=self.date, horizon_days=7, batch_size=2
        )
        self.assertEqual([day.pk for day in days], [day.pk for day in repeated])
        self.assertEqual(len(days), 2)
        self.assert_domain(
            'invalid_horizon',
            generate_horizon,
            actor_id=self.company.user_id,
            group_id=self.group.pk,
            start_date=self.date,
            horizon_days=0,
            batch_size=2,
        )

    def test_human_stop_order_is_saved_without_selecting_participants(self):
        stops = configure_stops(
            actor_id=self.company.user_id, service_id=self.outbound.pk, point_ids=[self.home.pk, self.garage.pk]
        )
        self.assertEqual([stop.point_id for stop in stops], [self.home.pk, self.garage.pk])
        self.assertFalse(self.travel().participations.exists())

    def test_point_change_invalidates_unpublished_calculation_and_preserves_snapshot(self):
        travel = self.ready_travel()
        # Regeneração automática é apenas para datas futuras; relógio volta à véspera.
        self.now = self.day.normal_deadline - timedelta(hours=1)
        old_snapshot = travel.current_snapshot
        old_input = old_snapshot.input_data
        configure_point(
            actor_id=self.company.user_id, company_id=self.company.pk, point_id=self.home.pk, latitude=-26.36
        )
        travel.refresh_from_db()
        old_snapshot.refresh_from_db()
        self.assertIsNone(travel.current_snapshot_id)
        self.assertEqual(old_snapshot.input_data, old_input)
        self.assertGreater(travel.revision, old_snapshot.revision)

    def test_assigning_vehicle_revalidates_capacity_without_automatic_choice(self):
        travel = self.ready_travel()
        replacement = configure_vehicle(
            actor_id=self.company.user_id,
            company_id=self.company.pk,
            plate='GHI3F45',
            capacity=3,
            garage_point_id=self.garage.pk,
        )
        result = assign_vehicle(actor_id=self.company.user_id, travel_id=travel.pk, vehicle_id=replacement.pk)
        self.assertEqual(result.vehicle_id, replacement.pk)
        self.assertEqual(result.planning_status, 'draft')

    def test_snapshot_period_requires_complete_ordered_pair(self):
        travel = self.ready_travel()
        for values in ({'planned_start': None}, {'planned_end': travel.current_snapshot.planned_start}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RouteSnapshot.objects.filter(pk=travel.current_snapshot_id).update(**values)
