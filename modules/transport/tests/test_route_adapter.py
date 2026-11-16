from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from modules.transport.osrm import OSRMError, route_coordinates


@override_settings(OSRM_URL='https://routing.invalid', OSRM_TIMEOUT_SECONDS=5, OSRM_MAX_SNAP_DISTANCE_METERS=500)
class RouteAdapterTests(SimpleTestCase):
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

    def test_fixed_two_point_segment_uses_route_provider_without_inventing_geometry(self):
        with patch('modules.transport.osrm.requests.get', return_value=self.response()) as provider:
            result = route_coordinates([[-48.8, -26.3], [-48.7, -26.2]])
        self.assertEqual(result['order'], [0, 1])
        self.assertEqual(result['duration_seconds'], 300)
        self.assertIn('/route/v1/driving/', provider.call_args.args[0])

    def test_invalid_provider_result_is_rejected_without_fallback(self):
        for changes in ({'code': 'NoRoute'}, {'routes': []}, {'waypoints': [{'distance': 1000}, {'distance': 0}]}):
            with (
                patch('modules.transport.osrm.requests.get', return_value=self.response(**changes)),
                self.assertRaises(OSRMError),
            ):
                route_coordinates([[-48.8, -26.3], [-48.7, -26.2]])

    def test_missing_provider_or_invalid_input_does_not_make_network_request(self):
        with patch('modules.transport.osrm.requests.get') as provider:
            with self.assertRaises(OSRMError):
                route_coordinates([[float('nan'), 0], [1, 2]])
            with override_settings(OSRM_URL=''), self.assertRaises(OSRMError):
                route_coordinates([[0, 0], [1, 2]])
        provider.assert_not_called()
