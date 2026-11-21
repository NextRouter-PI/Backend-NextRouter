"""Testes isolados do simulador modular de percurso de viagem."""

from django.test import TestCase, override_settings

from scripts.trip_simulator.database import prepare_scenario, reset_local_sqlite
from scripts.trip_simulator.scenarios import get_scenario, interpolate_route


class TripSimulatorTests(TestCase):
    def test_interpolate_route_distributes_points_evenly(self):
        coords = [(-48.8, -26.3), (-48.7, -26.4)]
        points = interpolate_route(coords, 5)
        self.assertEqual(len(points), 5)
        self.assertEqual(points[0], (-26.3, -48.8))
        self.assertEqual(points[-1], (-26.4, -48.7))
        self.assertEqual(points[2], (-26.35, -48.75))

    def test_reset_local_sqlite_requires_explicit_confirmation_and_dev_sqlite(self):
        with self.assertRaises(RuntimeError):
            reset_local_sqlite(confirm_fictitious=False)
        with override_settings(DEBUG=False), self.assertRaises(RuntimeError):
            reset_local_sqlite(confirm_fictitious=True)

    @override_settings(OSRM_URL='')
    def test_prepare_outbound_scenario_publishes_ready_travel(self):
        plan = prepare_scenario(get_scenario('outbound'))
        self.assertEqual(plan['scenario'], 'outbound')
        self.assertGreater(plan['travel_id'], 0)
        self.assertGreaterEqual(len(plan['geometry_coords']), 2)
        self.assertGreaterEqual(len(plan['stops']), 2)
        self.assertFalse(plan['used_osrm'])

    @override_settings(OSRM_URL='')
    def test_prepare_return_scenario_publishes_ready_travel(self):
        plan = prepare_scenario(get_scenario('return'))
        self.assertEqual(plan['scenario'], 'return')
        self.assertGreater(plan['travel_id'], 0)
        self.assertGreaterEqual(len(plan['geometry_coords']), 2)
        self.assertGreaterEqual(len(plan['stops']), 2)
        self.assertFalse(plan['used_osrm'])
