from rest_framework import serializers

from modules.organizations.models import OperationalPoint
from shared.api import InputModelSerializer

POINT_EDITABLE_FIELDS = (
    'point_type',
    'name',
    'street',
    'number',
    'complement',
    'neighborhood',
    'city',
    'state',
    'cep',
    'latitude',
    'longitude',
)


class PointSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationalPoint
        fields = ('id', 'company', *POINT_EDITABLE_FIELDS)


class PointInput(InputModelSerializer):
    class Meta:
        model = OperationalPoint
        fields = POINT_EDITABLE_FIELDS
