# core/serializers.py
from django.contrib.auth import get_user_model
from django.core.validators import MinLengthValidator
from django.db import transaction
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import Company, Driver, Passenger, User

User = get_user_model()


class UserSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'nome', 'telefone', 'tipo', 'foto', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    tipo = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)


class RegisterPassengerSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    nome = serializers.CharField(required=True)
    telefone = serializers.CharField(required=True)
    cpf = serializers.CharField(required=True, max_length=14)
    data_nascimento = serializers.DateField(required=True)
    genero = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    endereco = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cidade = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    estado = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    cep = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    empresa_id = serializers.IntegerField(required=False, allow_null=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email já está cadastrado.")
        return value

    def validate_cpf(self, value):
        if Passenger.objects.filter(cpf=value).exists():
            raise serializers.ValidationError("Este CPF já está cadastrado.")
        return value

    def validate_empresa_id(self, value):
        if value:
            if not Company.objects.filter(id=value).exists():
                raise serializers.ValidationError("Empresa não encontrada.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        cpf = validated_data.pop('cpf')
        data_nascimento = validated_data.pop('data_nascimento')
        genero = validated_data.pop('genero', None)
        endereco = validated_data.pop('endereco', None)
        cidade = validated_data.pop('cidade', None)
        estado = validated_data.pop('estado', None)
        cep = validated_data.pop('cep', None)
        empresa_id = validated_data.pop('empresa_id', None)
        email = validated_data.get('email')
        password = validated_data.pop('password')
        nome = validated_data.get('nome')
        telefone = validated_data.get('telefone')
        user = User.objects.create_user(
            email=email,
            password=password,
            nome=nome,
            telefone=telefone,
            tipo=User.TipoUsuario.PASSAGEIRO
        )
        empresa = None
        if empresa_id:
            try:
                empresa = Company.objects.get(id=empresa_id)
            except Company.DoesNotExist:
                pass

        passenger = Passenger.objects.create(
            user=user,
            cpf=cpf,
            data_nascimento=data_nascimento,
            genero=genero,
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep,
            empresa=empresa
        )
        return user


class RegisterDriverSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    nome = serializers.CharField(required=True)
    telefone = serializers.CharField(required=True)
    cpf = serializers.CharField(required=True, max_length=14)
    cnh = serializers.CharField(required=True, max_length=30)
    empresa_id = serializers.IntegerField(required=False, allow_null=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Este email já está cadastrado.")
        return value

    def validate_cpf(self, value):
        if Driver.objects.filter(cpf=value).exists():
            raise serializers.ValidationError("Este CPF já está cadastrado.")
        return value

    def validate_cnh(self, value):
        if Driver.objects.filter(cnh=value).exists():
            raise serializers.ValidationError("Esta CNH já está cadastrada.")
        return value

    def validate_empresa_id(self, value):
        if value:
            if not Company.objects.filter(id=value).exists():
                raise serializers.ValidationError("Empresa não encontrada.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        cpf = validated_data.pop('cpf')
        cnh = validated_data.pop('cnh')
        empresa_id = validated_data.pop('empresa_id', None)
        email = validated_data.get('email')
        password = validated_data.pop('password')
        nome = validated_data.get('nome')
        telefone = validated_data.get('telefone')
        user = User.objects.create_user(
            email=email,
            password=password,
            nome=nome,
            telefone=telefone,
            tipo=User.TipoUsuario.MOTORISTA
        )
        empresa = None
        if empresa_id:
            try:
                empresa = Company.objects.get(id=empresa_id)
            except Company.DoesNotExist:
                pass
        driver = Driver.objects.create(
            user=user,
            cpf=cpf,
            cnh=cnh,
            empresa=empresa,
            aprovado=False
        )
        return user
