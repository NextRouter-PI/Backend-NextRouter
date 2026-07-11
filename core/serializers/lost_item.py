from rest_framework import serializers

from core.models.lost_item import LostItem


class LostItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LostItem
        fields = '__all__'
