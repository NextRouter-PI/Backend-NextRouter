from rest_framework.serializers import ModelSerializer

from core.models import Driver_Job_Opening


class Driver_Job_OpeningSerializer(ModelSerializer):
    class Meta:
        model = Driver_Job_Opening
        fields = '__all__'
