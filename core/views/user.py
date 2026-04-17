# core/views.py
from django.contrib.auth import authenticate
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.authentication import generate_tokens_for_user
from core.models import Company, Driver, Passenger, User
from core.serializers import LoginSerializer, RegisterDriverSerializer, RegisterPassengerSerializer, UserSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in {'login', 'register_passenger', 'register_driver', 'create'}:
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(
        summary="Dados do usuário autenticado",
        description="Retorna os dados do usuário autenticado.",
        responses={200: UserSerializer, 401: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Retorna os dados do usuário autenticado."""
        user = request.user
        user_data = UserSerializer(user).data
        if hasattr(user, 'driver_profile'):
            user_data['perfil'] = {
                'tipo': 'motorista',
                'cpf': user.driver_profile.cpf,
                'cnh': user.driver_profile.cnh,
                'aprovado': user.driver_profile.aprovado,
                'empresa_id': user.driver_profile.empresa_id
            }
        elif hasattr(user, 'passenger_profile'):
            user_data['perfil'] = {
                'tipo': 'passageiro',
                'cpf': user.passenger_profile.cpf,
                'data_nascimento': user.passenger_profile.data_nascimento,
                'genero': user.passenger_profile.genero,
                'endereco': user.passenger_profile.endereco,
                'cidade': user.passenger_profile.cidade,
                'estado': user.passenger_profile.estado,
                'cep': user.passenger_profile.cep,
                'empresa_id': user.passenger_profile.empresa_id
            }
        return Response(user_data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Login de usuário",
        description="Autentica o usuário e retorna tokens JWT.",
        request=LoginSerializer,
        responses={200: LoginSerializer, 401: None},
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """Login de usuário com email e senha."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            username=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )

        if user is None:
            return Response(
                {'error': 'Email ou senha incorretos.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        tokens = generate_tokens_for_user(user)
        profile_data = {}
        if hasattr(user, 'driver_profile'):
            profile_data = {
                'cpf': user.driver_profile.cpf,
                'cnh': user.driver_profile.cnh,
                'aprovado': user.driver_profile.aprovado
            }
        elif hasattr(user, 'passenger_profile'):
            profile_data = {
                'cpf': user.passenger_profile.cpf,
                'data_nascimento': user.passenger_profile.data_nascimento
            }

        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': {
                'id': user.id,
                'email': user.email,
                'nome': user.nome if hasattr(user, 'nome') else '',
                'tipo': user.tipo,
                'telefone': user.telefone if hasattr(user, 'telefone') else '',
                **profile_data
            },
            'tipo': user.tipo,
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Cadastro de Passageiro",
        description="Cria uma nova conta de passageiro com User e Passenger.",
        request=RegisterPassengerSerializer,
        responses={201: RegisterPassengerSerializer, 400: None},
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_passenger(self, request):
        """Cadastro de novo passageiro (cria User e Passenger)."""
        serializer = RegisterPassengerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = generate_tokens_for_user(user)
        passenger = Passenger.objects.get(user=user)
        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': {
                'id': user.id,
                'email': user.email,
                'nome': user.nome,
                'telefone': user.telefone,
                'tipo': user.tipo,
                'cpf': passenger.cpf,
                'data_nascimento': passenger.data_nascimento,
                'genero': passenger.genero,
                'endereco': passenger.endereco,
                'cidade': passenger.cidade,
                'estado': passenger.estado,
                'cep': passenger.cep,
            },
            'tipo': user.tipo,
            'message': 'Conta de passageiro criada com sucesso!'
        }, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Cadastro de Motorista",
        description="Cria uma nova conta de motorista com User e Driver.",
        request=RegisterDriverSerializer,
        responses={201: RegisterDriverSerializer, 400: None},
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register_driver(self, request):
        """Cadastro de novo motorista (cria User e Driver)."""
        serializer = RegisterDriverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = generate_tokens_for_user(user)
        driver = Driver.objects.get(user=user)
        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': {
                'id': user.id,
                'email': user.email,
                'nome': user.nome,
                'telefone': user.telefone,
                'tipo': user.tipo,
                'cpf': driver.cpf,
                'cnh': driver.cnh,
                'aprovado': driver.aprovado,
            },
            'tipo': user.tipo,
            'message': 'Conta de motorista criada com sucesso! Aguardando aprovação.'
        }, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Status de aprovação do motorista",
        description="Retorna o status de aprovação do motorista autenticado.",
        responses={200: None, 401: None, 404: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def status_motorista(self, request):
        """Retorna status de aprovação se for motorista."""
        user = request.user
        if not user.is_motorista:
            return Response(
                {'error': 'Usuário não é motorista.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if hasattr(user, 'driver_profile'):
            return Response({
                'aprovado': user.driver_profile.aprovado,
                'status': 'aprovado' if user.driver_profile.aprovado else 'pendente'
            }, status=status.HTTP_200_OK)
        return Response(
            {'error': 'Perfil de motorista não encontrado.'},
            status=status.HTTP_404_NOT_FOUND
        )
    