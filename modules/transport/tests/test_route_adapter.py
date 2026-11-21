from unittest.mock import Mock, patch

import httpx
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from modules.transport.osrm import OSRMError, optimize_coordinates, route_coordinates


@override_settings(
    OSRM_URL='https://routing.invalid',
    OSRM_TIMEOUT_SECONDS=5,
    OSRM_MAX_ATTEMPTS=2,
    OSRM_MAX_SNAP_DISTANCE_METERS=500,
)
class RouteAdapterTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def response(self, **changes):
        payload = {
            'code': 'Ok',
            'waypoints': [{'distance': 0}, {'distance': 0}],
            'routes': [
                {
                    'distance': 1000,
                    'duration': 300,
                    'geometry': {'type': 'LineString', 'coordinates': [[-48.8, -26.3], [-48.7, -26.2]]},
                }
            ],
        }
        payload.update(changes)
        response = Mock()
        response.json.return_value = payload
        return response

    def trip_response(self, **changes):
        payload = {
            'code': 'Ok',
            'waypoints': [
                {'distance': 0, 'waypoint_index': 0},
                {'distance': 0, 'waypoint_index': 1},
                {'distance': 0, 'waypoint_index': 2},
            ],
            'trips': [
                {
                    'distance': 2500,
                    'duration': 600,
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [[-48.8, -26.3], [-48.75, -26.25], [-48.7, -26.2]],
                    },
                }
            ],
        }
        payload.update(changes)
        response = Mock()
        response.json.return_value = payload
        return response

    def _mock_client(self, *, return_value=None, side_effect=None):
        client = Mock()
        if side_effect is not None:
            client.get.side_effect = side_effect
        else:
            client.get.return_value = return_value
        return client

    def test_fixed_two_point_segment_uses_route_provider_without_inventing_geometry(self):
        client = self._mock_client(return_value=self.response())
        with patch('modules.transport.osrm.get_http_client', return_value=client):
            result = route_coordinates([[-48.8, -26.3], [-48.7, -26.2]])
            cached = route_coordinates([[-48.8, -26.3], [-48.7, -26.2]])
        self.assertEqual(result['order'], [0, 1])
        self.assertEqual(result['duration_seconds'], 300)
        self.assertEqual(cached, result)
        self.assertEqual(client.get.call_count, 1)
        self.assertIn('/route/v1/driving/', client.get.call_args.args[0])

    def test_invalid_provider_result_is_rejected_without_fallback(self):
        for changes in ({'code': 'NoRoute'}, {'routes': []}, {'waypoints': [{'distance': 1000}, {'distance': 0}]}):
            cache.clear()
            client = self._mock_client(return_value=self.response(**changes))
            with (
                patch('modules.transport.osrm.get_http_client', return_value=client),
                self.assertRaises(OSRMError),
            ):
                route_coordinates([[-48.8, -26.3], [-48.7, -26.2]])

    def test_missing_provider_or_invalid_input_does_not_make_network_request(self):
        client = self._mock_client()
        with patch('modules.transport.osrm.get_http_client', return_value=client):
            with self.assertRaises(OSRMError):
                route_coordinates([[float('nan'), 0], [1, 2]])
            with self.assertRaises(OSRMError):
                route_coordinates([[True, 0], [1, 2]])
            with override_settings(OSRM_URL=''), self.assertRaises(OSRMError):
                route_coordinates([[0, 0], [1, 2]])
        client.get.assert_not_called()

    def test_optimize_coordinates_retries_on_transient_network_error_and_caches(self):
        client = self._mock_client(side_effect=[httpx.ReadTimeout('timeout'), self.trip_response()])
        coords = [[-48.8, -26.3], [-48.75, -26.25], [-48.7, -26.2]]
        with patch('modules.transport.osrm.get_http_client', return_value=client):
            result = optimize_coordinates(coords)
            cached = optimize_coordinates(coords)
        self.assertEqual(result['order'], [0, 1, 2])
        self.assertEqual(cached, result)
        self.assertEqual(client.get.call_count, 2)
