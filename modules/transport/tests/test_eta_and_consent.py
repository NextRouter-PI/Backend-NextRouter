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


class ApproachRouteTests(ServiceTestCase):
    def test_route_goes_from_driver_position_through_open_stops_and_skips_boarded(self):
        from unittest.mock import patch

        from modules.transport.services.execution.attendance import record_participation
        from modules.transport.services.tracking import approach_route

        travel = self.ready_travel()
        self.publish(travel)
        travel = start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        self.assert_domain('position_missing', approach_route, actor_id=self.driver.user_id, travel_id=travel.pk)
        save_location(
            actor_id=self.driver.user_id,
            travel_id=travel.pk,
            latitude=-26.3,
            longitude=-48.8,
            recorded_at=self.now,
            max_future_skew=timedelta(seconds=5),
        )
        stops = list(travel.published_snapshot.stops.order_by('position'))
        with patch('modules.transport.osrm.route_coordinates', side_effect=self.route_result):
            legs = approach_route(actor_id=self.driver.user_id, travel_id=travel.pk)['legs']
        self.assertEqual([leg['stop_id'] for leg in legs], [stop.pk for stop in stops])
        self.assertEqual(legs[0]['geometry']['coordinates'][0], [-48.8, -26.3])

        # Embarcou: o primeiro trecho passa a ir direto para a parada seguinte.
        participation = travel.participations.get()
        record_participation(
            actor_id=self.driver.user_id,
            participation_id=participation.pk,
            kind='boarded',
            operation_id='00000000-0000-4000-8000-000000000001',
        )
        with patch('modules.transport.osrm.route_coordinates', side_effect=self.route_result):
            legs = approach_route(actor_id=self.driver.user_id, travel_id=travel.pk)['legs']
        self.assertEqual([leg['stop_id'] for leg in legs], [stop.pk for stop in stops[1:]])
        self.assertEqual(legs[0]['geometry']['coordinates'][0], [-48.8, -26.3])
        self.assert_domain('permission_denied', approach_route, actor_id=self.company.user_id, travel_id=travel.pk)


class LiveExpectationTests(ServiceTestCase):
    def test_expected_time_follows_driver_position_and_can_go_below_planned(self):
        from unittest.mock import patch

        from modules.transport.services.eta import planned_at, stop_expectations

        travel = self.ready_travel()
        self.publish(travel)
        travel = start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        save_location(
            actor_id=self.driver.user_id,
            travel_id=travel.pk,
            latitude=-26.3,
            longitude=-48.8,
            recorded_at=self.now,
            max_future_skew=timedelta(seconds=5),
        )
        travel.refresh_from_db()
        snapshot = travel.published_snapshot
        stops = list(snapshot.stops.order_by('position'))

        def leg(coordinates, **kwargs):
            return {**self.route_result(coordinates), 'duration_seconds': 120}

        with patch('modules.transport.osrm.route_coordinates', side_effect=leg):
            expected, _ = stop_expectations(snapshot, stops, now=self.now)
        # Agora + 2 min por trecho, parada a parada, a partir da posição atual.
        self.assertEqual(expected[stops[0].pk], self.now + timedelta(minutes=2))
        self.assertEqual(expected[stops[-1].pk], self.now + timedelta(minutes=2 * len(stops)))
        # Mais cedo que o previsto quando o motorista está adiantado (não fica preso ao previsto).
        self.assertLess(expected[stops[0].pk], planned_at(stops[0]) + timedelta(hours=1))

    def test_without_routing_service_falls_back_to_planned_plus_delay(self):
        from modules.transport.services.eta import expected_at, stop_expectations, travel_delay_seconds

        travel = self.ready_travel()
        self.publish(travel)
        travel = start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        snapshot = travel.published_snapshot
        stops = list(snapshot.stops.order_by('position'))
        expected, delay = stop_expectations(snapshot, stops, now=self.now)
        self.assertEqual(delay, travel_delay_seconds(snapshot, stops, now=self.now))
        self.assertEqual(expected[stops[0].pk], expected_at(stops[0], delay))


class PassengerRouteTests(ServiceTestCase):
    def test_passenger_sees_path_to_own_stop_then_to_destination(self):
        from unittest.mock import patch

        from modules.transport.services.execution.attendance import record_participation
        from modules.transport.services.tracking import passenger_route

        travel = self.ready_travel()
        self.publish(travel)
        travel = start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)
        participation = travel.participations.get()
        user_id = participation.eligibility.passenger.user_id
        empty = {'to_me': None, 'to_destination': None}
        self.assertEqual(passenger_route(actor_id=user_id, participation_id=participation.pk), empty)
        save_location(
            actor_id=self.driver.user_id,
            travel_id=travel.pk,
            latitude=-26.3,
            longitude=-48.8,
            recorded_at=self.now,
            max_future_skew=timedelta(seconds=5),
        )
        with patch('modules.transport.osrm.route_coordinates', side_effect=self.route_result):
            route = passenger_route(actor_id=user_id, participation_id=participation.pk)
        self.assertEqual(route['to_me']['coordinates'][0], [-48.8, -26.3])
        self.assertIsNotNone(route['to_destination'])
        self.assertEqual(route['to_me']['coordinates'][-1], route['to_destination']['coordinates'][0])
        self.assert_domain(
            'permission_denied', passenger_route, actor_id=self.driver.user_id, participation_id=participation.pk
        )

        record_participation(
            actor_id=self.driver.user_id,
            participation_id=participation.pk,
            kind='boarded',
            operation_id='00000000-0000-4000-8000-000000000002',
        )
        with patch('modules.transport.osrm.route_coordinates', side_effect=self.route_result):
            route = passenger_route(actor_id=user_id, participation_id=participation.pk)
        self.assertIsNone(route['to_me'])
        self.assertEqual(route['to_destination']['coordinates'][0], [-48.8, -26.3])
