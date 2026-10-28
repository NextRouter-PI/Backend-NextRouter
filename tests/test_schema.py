from django.test import SimpleTestCase
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator


class OpenApiContractTests(SimpleTestCase):
    def test_schema_has_no_generation_warnings_and_documents_operations(self):
        GENERATOR_STATS.reset()
        with GENERATOR_STATS.silence():
            schema = SchemaGenerator().get_schema(public=True)
        self.assertFalse(GENERATOR_STATS._warn_cache, list(GENERATOR_STATS._warn_cache))
        self.assertFalse(GENERATOR_STATS._error_cache, list(GENERATOR_STATS._error_cache))

        operations = [
            operation
            for path in schema['paths'].values()
            for method, operation in path.items()
            if method in {'get', 'post', 'put', 'patch', 'delete'}
        ]
        self.assertGreater(len(operations), 0)
        self.assertEqual(len({op['operationId'] for op in operations}), len(operations))
        for operation in operations:
            self.assertTrue(operation.get('summary'), operation['operationId'])
            self.assertTrue(operation.get('description'), operation['operationId'])
            self.assertTrue(operation.get('tags'), operation['operationId'])

        self.assertIn('202', schema['paths']['/api/paths/{id}/optimize/']['post']['responses'])
        self.assertIn('400', schema['paths']['/api/travels/']['post']['responses'])
