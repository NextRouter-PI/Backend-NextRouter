from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import Empresa, Motorista, User


class MotoristaSerializer(ModelSerializer):
    class Meta:
        model = Motorista
        fields = "__all__"


class RegistroMotoristaSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    telefone = serializers.CharField(required=False)
    cpf = serializers.CharField(required=False)
    cnh = serializers.CharField(required=False)
    data_nascimento = serializers.DateField(required=False)
    genero = serializers.CharField(required=False)
    endereco = serializers.CharField(required=False)
    cidade = serializers.CharField(required=False)
    estado = serializers.CharField(required=False)
    cep = serializers.CharField(required=False)

    empresa = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "password",
            "telefone",
            "cpf",
            "cnh",
            "data_nascimento",
            "genero",
            "endereco",
            "cidade",
            "estado",
            "cep",
            "empresa",
        ]

    def create(self, validated_data):
        telefone = validated_data.pop("telefone", None)
        cpf = validated_data.pop("cpf", None)
        cnh = validated_data.pop("cnh", None)
        data_nascimento = validated_data.pop("data_nascimento", None)
        genero = validated_data.pop("genero", None)
        endereco = validated_data.pop("endereco", None)
        cidade = validated_data.pop("cidade", None)
        estado = validated_data.pop("estado", None)
        cep = validated_data.pop("cep", None)
        empresa_nome = validated_data.pop("empresa", None)

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data.get("name"),
            type="Motorista",
        )

        motorista = Motorista.objects.create(
            user=user,
            telefone=telefone,
            cpf=cpf,
            cnh=cnh,
            data_nascimento=data_nascimento,
            genero=genero,
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep,
        )

        if empresa_nome:
            Empresa.objects.create(
                name=empresa_nome,
                motorista=motorista
            )

        return user
