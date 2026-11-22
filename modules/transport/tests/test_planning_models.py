import uuid
from datetime import timedelta
from unittest import mock

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory

from modules.organizations.models import CompanyMembership, Driver, PassengerGroupMembership
from modules.transport import models
from tests.helpers import create_passenger, create_user

from .helpers import DayModelTestCase


class PlanningModelTestCase(DayModelTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.travel = models.Travel.objects.create(
            company=cls.company,
            service_day=cls.day,
            service=cls.service,
            planned_start=cls.now + timedelta(hours=3),
            planned_end=cls.now + timedelta(hours=4),
        )
        cls.point_data = {'latitude': -26.3, 'longitude': -48.8}
        cls.snapshot = models.RouteSnapshot.objects.create(
            travel=cls.travel,
            revision=1,
            base_revision=1,
            input_data={'point': cls.point_data},
            origin=cls.point_data,
            destination=cls.point_data,
            created_at=cls.now,
        )

    def ready_snapshot(self):
        self.snapshot.state = 'ready'
        self.snapshot.geometry = {'type': 'LineString', 'coordinates': [[-48.8, -26.3], [-48.7, -26.2]]}
        self.snapshot.distance_meters = 1000
        self.snapshot.duration_seconds = 120
        self.snapshot.calculated_at = self.now
        self.snapshot.save()
        return self.snapshot


class PlanningModelTests(PlanningModelTestCase):
    def test_ready_snapshot_has_metrics_geometry_and_frozen_points(self):
        self.ready_snapshot().full_clean()
        self.point.street = 'Outra rua fictícia'
        self.point.save(update_fields=['street'])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.origin, self.point_data)

    def test_database_requires_complete_ready_result_and_unique_revision(self):
        for changes in ({'state': 'ready'}, {'revision': 0}, {'distance_meters': -1}, {'duration_seconds': -1}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                models.RouteSnapshot.objects.filter(pk=self.snapshot.pk).update(**changes)
        self.assert_db_rejects(models.RouteSnapshot, travel=self.travel, revision=1, base_revision=1)

    def test_full_clean_rejects_invalid_geometry_and_coordinates(self):
        snapshot = self.ready_snapshot()
        for coordinates in (
            [[0, 91], [1, 2]],
            [[True, 0], [1, 2]],
            [[float('nan'), 0], [1, 2]],
            [[10**500, 0], [1, 2]],
        ):
            snapshot.geometry = {'type': 'LineString', 'coordinates': coordinates}
            with self.subTest(coordinates=coordinates), self.assertRaises(ValidationError):
                snapshot.full_clean()

    def test_stops_are_ordered_and_handle_execution_explicitly(self):
        stop = models.RouteStop.objects.create(snapshot=self.snapshot, position=1, point_snapshot=self.point_data)
        stop.full_clean()
        self.assert_db_rejects(models.RouteStop, snapshot=self.snapshot, position=1, point_snapshot=self.point_data)
        self.assert_db_rejects(models.RouteStop, snapshot=self.snapshot, position=0, point_snapshot=self.point_data)
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.RouteStop.objects.filter(pk=stop.pk).update(state='completed')

    def test_stop_can_link_boarding_and_drop_events_without_duplicate_coordinates(self):
        stop = models.RouteStop.objects.create(snapshot=self.snapshot, position=1, point_snapshot=self.point_data)
        participation = models.TravelParticipation.objects.create(
            travel=self.travel,
            eligibility=self.eligibility,
            leg='outbound',
            allocated_at=self.now,
        )
        for operation in ('board', 'drop'):
            models.RouteStopParticipant.objects.create(
                stop=stop,
                participation=participation,
                operation=operation,
            ).full_clean()
        self.assertEqual(stop.participants.count(), 2)
        self.assertEqual(self.snapshot.stops.count(), 1)

    def test_publication_retains_snapshot_and_audit(self):
        self.ready_snapshot()
        publication = models.TravelPublication.objects.create(
            travel=self.travel,
            snapshot=self.snapshot,
            revision=1,
            published_by=self.company.user,
        )
        publication.full_clean()
        with self.assertRaises(ProtectedError):
            self.snapshot.delete()
        self.travel.published_snapshot = self.snapshot
        self.travel.published_revision = 1
        self.travel.current_snapshot = self.snapshot
        self.travel.save()
        self.travel.full_clean()

    def test_multiple_passengers_share_one_physical_stop(self):
        passenger = create_passenger('shared-stop-passenger@example.com')
        membership = CompanyMembership.objects.create(
            company=self.company,
            passenger=passenger,
            requested_by=passenger.user,
            created_at=self.now,
            status='active',
            reviewed_at=self.now,
            reviewed_by=self.company.user,
        )
        group_membership = PassengerGroupMembership.objects.create(
            membership=membership,
            route_group=self.group,
            transport_point=self.point,
            assigned_by=self.company.user,
            started_at=self.now,
        )
        eligibility = models.ServiceDayEligibility.objects.create(
            day=self.day,
            passenger=passenger,
            group_membership=group_membership,
            authorized_service_ids=[self.service.pk],
            point_snapshot=self.point_data,
        )
        stop = models.RouteStop.objects.create(snapshot=self.snapshot, position=1, point_snapshot=self.point_data)
        for eligible in (self.eligibility, eligibility):
            participation = models.TravelParticipation.objects.create(
                travel=self.travel,
                eligibility=eligible,
                leg='outbound',
                allocated_at=self.now,
            )
            participation.full_clean()
            models.RouteStopParticipant.objects.create(stop=stop, participation=participation, operation='board')
        self.assertEqual(stop.participants.count(), 2)
        self.assertEqual(self.snapshot.stops.count(), 1)

    def test_effective_leg_cannot_be_allocated_to_two_different_services(self):
        models.TravelParticipation.objects.create(
            travel=self.travel,
            eligibility=self.eligibility,
            leg='outbound',
            allocated_at=self.now,
        )
        service = models.RecurringService.objects.create(
            route_group=self.group,
            name='Outra ida',
            direction='outbound',
            weekdays=31,
            target_time='09:00',
            valid_from=self.tomorrow,
            created_by=self.company.user,
        )
        other_travel = models.Travel.objects.create(
            company=self.company,
            service_day=self.day,
            service=service,
            planned_start=self.travel.planned_start,
            planned_end=self.travel.planned_end,
        )
        self.assert_db_rejects(
            models.TravelParticipation,
            travel=other_travel,
            eligibility=self.eligibility,
            leg='outbound',
        )

    def test_unready_snapshot_cannot_be_published_by_validation(self):
        with self.assertRaises(ValidationError):
            models.TravelPublication(
                travel=self.travel,
                snapshot=self.snapshot,
                revision=1,
                published_by=self.company.user,
            ).full_clean()

    def test_revision_jobs_have_frozen_input_and_require_claim_when_running(self):
        job = models.RouteOptimizationJob.objects.create(
            snapshot=self.snapshot,
            input_revision=1,
            frozen_input=self.snapshot.input_data,
        )
        job.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.RouteOptimizationJob.objects.filter(pk=job.pk).update(status='running')
        job.status = 'running'
        job.claim_token = uuid.uuid4()
        job.claim_expires_at = self.now + timedelta(minutes=1)
        job.save()
        job.full_clean()
        job.frozen_input = {'other': True}
        with self.assertRaises(ValidationError):
            job.full_clean()

    def test_worker_runs_with_default_limits_and_rejects_conflicting_company_scope(self):
        job = models.RouteOptimizationJob.objects.create(
            snapshot=self.snapshot,
            input_revision=1,
            frozen_input=self.snapshot.input_data,
        )
        with mock.patch('modules.transport.management.commands.process_route_jobs.claim_snapshot_job') as claim:
            with self.assertRaises(CommandError):
                call_command('process_route_jobs', once=True, all_companies=True, company_id=self.company.pk)
            claim.assert_not_called()
            claim.return_value = None
            call_command('process_route_jobs', once=True)
            self.assertGreaterEqual(claim.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')


class CommunicationModelTests(PlanningModelTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.driver = Driver.objects.create(user=create_user('stage1-driver@example.com'))
        cls.driver_membership = CompanyMembership.objects.create(
            company=cls.company,
            driver=cls.driver,
            requested_by=cls.driver.user,
            created_at=cls.now,
            status='active',
            reviewed_at=cls.now,
            reviewed_by=cls.company.user,
        )

    def invitation_data(self, **extra):
        return {
            'travel': self.travel,
            'driver_membership': self.driver_membership,
            'invited_by': self.company.user,
            'created_at': self.now,
            'expires_at': self.now + timedelta(hours=1),
            **extra,
        }

    def test_invitation_pending_is_not_acceptance_and_only_one_is_current(self):
        invitation = models.DriverInvitation.objects.create(**self.invitation_data())
        invitation.full_clean()
        self.assertIsNone(invitation.responded_at)
        self.assertEqual(invitation.status, 'pending')
        self.assert_db_rejects(models.DriverInvitation, **self.invitation_data())
        invitation.is_current = False
        invitation.status = 'revoked'
        invitation.closed_at = self.now
        invitation.save()
        models.DriverInvitation.objects.create(**self.invitation_data()).full_clean()

    def test_ready_current_published_revision_allows_start_but_rejects_stale_revision(self):
        self.ready_snapshot()
        self.travel.driver = self.driver
        self.travel.vehicle = self.vehicle
        self.travel.current_snapshot = self.snapshot
        self.travel.published_snapshot = self.snapshot
        self.travel.published_revision = 1
        self.travel.planning_status = 'ready'
        self.travel.status = 'in_progress'
        self.travel.started_at = self.now
        self.travel.save()
        self.travel.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Travel.objects.filter(pk=self.travel.pk).update(revision=2)

    def test_acceptance_requires_invited_actor_and_valid_deadline(self):
        self.assert_db_rejects(models.DriverInvitation, **self.invitation_data(status='accepted'))
        data = self.invitation_data(
            status='accepted',
            responded_at=self.now,
            responded_by=self.driver.user,
            closed_at=self.now,
        )
        invitation = models.DriverInvitation.objects.create(**data)
        invitation.full_clean()
        invitation.responded_by = self.company.user
        with self.assertRaises(ValidationError):
            invitation.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.DriverInvitation.objects.filter(pk=invitation.pk).update(responded_at=invitation.expires_at)

    def notice_data(self, **extra):
        return {
            'recipient': self.passenger.user,
            'kind': 'publication',
            'resource_type': 'travel',
            'resource_id': str(self.travel.pk),
            'deduplication_key': 'publication:1:1',
            'created_at': self.now,
            'payload': {'revision': 1, 'status': 'published'},
            **extra,
        }

    def test_persistent_notice_deduplicates_per_recipient_and_tracks_reading(self):
        notice = models.Notification.objects.create(**self.notice_data())
        notice.full_clean()
        self.assert_db_rejects(models.Notification, **self.notice_data())
        models.Notification.objects.create(**self.notice_data(recipient=self.company.user)).full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            models.Notification.objects.filter(pk=notice.pk).update(read_at=self.now - timedelta(seconds=1))

    def test_notice_rejects_personal_payload_and_invalid_metadata(self):
        for payload in ({'address': 'Endereço fictício'}, {'status': 'Endereço fictício'}, {'revision': True}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                models.Notification(**self.notice_data(payload=payload)).full_clean()
        self.assert_db_rejects(models.Notification, **self.notice_data(kind='invalid'))

    def test_all_new_model_admins_block_writes(self):
        request = RequestFactory().get('/admin/')
        request.user = self.company.user
        for model in (
            models.RecurringService,
            models.PassengerServiceAuthorization,
            models.RecurringServiceStop,
            models.ResponsePolicy,
            models.ServiceDay,
            models.ServiceDayEligibility,
            models.DailyResponse,
            models.DailyChangeRequest,
            models.TravelParticipation,
            models.ParticipationEvent,
            models.SeatReservation,
            models.RouteSnapshot,
            models.RouteStop,
            models.RouteStopParticipant,
            models.TravelPublication,
            models.DriverInvitation,
            models.Notification,
            models.RouteOptimizationJob,
        ):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_add_permission(request))
                self.assertFalse(model_admin.has_change_permission(request))
                self.assertFalse(model_admin.has_delete_permission(request))
