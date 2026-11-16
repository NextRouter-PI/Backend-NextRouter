from datetime import timedelta

from django.db import transaction

from modules.transport.services.demand import withdraw_leg
from modules.transport.services.execution import finish_travel, start_travel
from modules.transport.services.tracking import read_location, save_location

from .service_helpers import ServiceTestCase


class TrackingServiceTests(ServiceTestCase):
    def running(self):
        travel = self.ready_travel()
        self.publish(travel)
        return start_travel(actor_id=self.driver.user_id, travel_id=travel.pk, expected_revision=travel.revision)

    def save(self, travel, **extra):
        return save_location(**{
            'actor_id': self.driver.user_id,
            'travel_id': travel.pk,
            'latitude': -26.3,
            'longitude': -48.8,
            'recorded_at': self.now,
            'max_future_skew': timedelta(seconds=5),
            **extra,
        })

    def test_position_requires_allocation_and_shows_staleness_without_faking_current_position(self):
        travel = self.running()
        self.assertEqual(
            read_location(actor_id=self.passenger.user_id, travel_id=travel.pk), {'position': None, 'stale': True}
        )
        self.save(travel)
        result = read_location(actor_id=self.passenger.user_id, travel_id=travel.pk)
        self.assertFalse(result['stale'])
        self.assert_domain('permission_denied', read_location, actor_id=self.other.user_id, travel_id=travel.pk)
        self.now += timedelta(hours=1)
        self.assertTrue(read_location(actor_id=self.passenger.user_id, travel_id=travel.pk)['stale'])

    def test_withdrawal_removes_live_access_and_finish_clears_position(self):
        travel = self.running()
        self.save(travel)
        withdraw_leg(actor_id=self.passenger.user_id, eligibility_id=self.eligibility.pk, leg='outbound')
        self.assert_domain('permission_denied', read_location, actor_id=self.passenger.user_id, travel_id=travel.pk)
        finish_travel(actor_id=self.driver.user_id, travel_id=travel.pk)
        travel.refresh_from_db()
        self.assertIsNone(travel.current_latitude)
        self.assertIsNone(travel.location_updated_at)
        self.assert_domain('travel_not_active', read_location, actor_id=self.company.user_id, travel_id=travel.pk)

    def test_wrong_driver_and_out_of_order_positions_are_rejected(self):
        travel = self.running()
        self.assert_domain('permission_denied', self.save, travel=travel, actor_id=self.passenger.user_id)
        self.save(travel)
        self.assert_domain('out_of_order', self.save, travel=travel)
        self.assert_domain('invalid_coordinates', self.save, travel=travel, latitude=float('nan'))
        self.assert_domain('invalid_coordinates', self.save, travel=travel, latitude=10**500)

    def test_delivery_only_occurs_after_commit_and_rollbacks_do_not_deliver(self):
        travel = self.running()
        delivered = []
        with transaction.atomic():
            self.save(travel, deliver=lambda *args: delivered.append(args))
            self.assertEqual(delivered, [])
        self.assertEqual(len(delivered), 1)
        self.now += timedelta(minutes=1)
        try:
            with transaction.atomic():
                self.save(travel, deliver=lambda *args: delivered.append(args))
                raise RuntimeError('Rollback fictício')
        except RuntimeError:
            pass
        self.assertEqual(len(delivered), 1)
