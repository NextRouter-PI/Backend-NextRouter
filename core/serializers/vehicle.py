from rest_framework import serializers


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ['garage', 'group_id']
