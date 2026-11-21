from rest_framework import serializers


class EmailChangeCodeSerializer(serializers.Serializer):
    code = serializers.RegexField(r'^\d{6}$')


class EmailChangeConfirmSerializer(EmailChangeCodeSerializer):
    password = serializers.CharField(write_only=True)
