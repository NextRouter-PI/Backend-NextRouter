from datetime import timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase

from modules.transport.services.eta import expected_at, planned_at, travel_delay_seconds
from modules.transport.services.execution import start_travel
from modules.transport.services.routing import stop_offsets
from modules.transport.services.tracking import save_location

from .service_helpers import ServiceTestCase


class StopOffsetsTests(SimpleTestCase):
    def test_offsets_accumulate_leg_durations(self):
        result = {'duration_seconds': 600, 'leg_seconds': [120.4, 300, 179.6]}
        self.assertEqual(stop_offsets(result, 4), [0, 120, 420, 600])

    def test_missing_legs_spread_total_evenly(self):
        self.assertEqual(stop_offsets({'duration_seconds': 600}, 4), [0, 200, 400, 600])


class DelayTests(SimpleTestCase):
    def setUp(self):
        from datetime import UTC, datetime

        self.start = datetime(2026, 11, 15, 7, tzinfo=UTC)

    def stop(self, position, minutes, handled_minutes=None):
        planned = (self.start + timedelta(minutes=minutes)).isoformat()
        handled = self.start + timedelta(minutes=handled_minutes) if handled_minutes is not None else None
        return SimpleNamespace(position=position, point_snapshot={'_planned_at': planned}, handled_at=handled)

    def snapshot(self, status='in_progress', started=0):
        travel = SimpleNamespace(status=status, started_at=self.start + timedelta(minutes=started))
        return SimpleNamespace(travel=travel, planned_start=self.start)

    def test_delay_follows_last_handled_stop_and_shifts_pending_ones(self):
        stops = [self.stop(1, 5, handled_minutes=9), self.stop(2, 12)]
        delay = travel_delay_seconds(self.snapshot(), stops, now=self.start + timedelta(minutes=10))
        self.assertEqual(delay, 240)
        self.assertEqual(expected_at(stops[1], delay), planned_at(stops[1]) + timedelta(minutes=4))
        self.assertEqual(expected_at(stops[0], delay), stops[0].handled_at)

    def test_overdue_next_stop_raises_delay_and_finished_travel_has_none(self):
        stops = [self.stop(1, 5)]
        self.assertEqual(travel_delay_seconds(self.snapshot(), stops, now=self.start + timedelta(minutes=8)), 180)
        self.assertEqual(travel_delay_seconds(self.snapshot(status='finished'), stops), 0)


class LocationConsentTests(ServiceTestCase):
    def test_position_is_refused_without_consent(self):
        travel = self.ready_travel()
        self.publish(travel)
        travel = start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        self.driver.location_consent_at = None
        self.driver.save(update_fields=['location_consent_at'])
        self.assert_domain(
            'location_consent_required',
            lambda: save_location(
                actor_id=self.driver.user_id,
                travel_id=travel.pk,
                latitude=-26.3,
                longitude=-48.8,
                recorded_at=self.now,
                max_future_skew=timedelta(seconds=5),
            ),
        )
