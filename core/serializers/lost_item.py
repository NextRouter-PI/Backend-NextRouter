from rest_framework import serializers

from core.models.lost_item import LostItem


class LostItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItem
        fields = ['item_description', 'route_id']
