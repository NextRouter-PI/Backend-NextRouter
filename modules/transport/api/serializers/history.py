from rest_framework import serializers

from modules.transport.models import DriverRating, LostItem, LostItemEvent
from shared.api import InputSerializer, OperationInput


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverRating
        fields = ('id', 'driver', 'travel', 'score', 'comment', 'created_at')


class RatingInput(InputSerializer):
    travel_id = serializers.IntegerField(min_value=1)
    score = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=500, allow_blank=True, default='')


class LostItemEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItemEvent
        fields = ('id', 'status', 'actor', 'occurred_at', 'operation_id')


class LostItemSerializer(serializers.ModelSerializer):
    events = LostItemEventSerializer(many=True, read_only=True)

    class Meta:
        model = LostItem
        fields = ('id', 'travel', 'item_description', 'status', 'created_at', 'events')


class LostItemInput(OperationInput):
    travel_id = serializers.IntegerField(min_value=1)
    item_description = serializers.CharField(max_length=255)


class CustodyInput(OperationInput):
    target_status = serializers.ChoiceField(choices=['found', 'returned'])
