from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.authentication import generate_tokens_for_user
from core.models import Company, Passenger, User
from core.serializers import LoginSerializer, RegisterSerializer, UserSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action in {'login', 'register', 'create'}:
            return [AllowAny()]
        return [IsAuthenticated()]

    @extend_schema(
        summary="Dados do usuário autenticado",
        description="Retorna os dados do usuário autenticado.",
        responses={200: UserSerializer, 401: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """ Retorna os dados do usuário autenticado."""
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Login de usuário",
        description="Autentica o usuário e retorna tokens JWT.",
        request=LoginSerializer,
        responses={200: LoginSerializer, 401: None},
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def login(self, request):
        """.Login de usuário com email e senha."""
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
        response_serializer = LoginSerializer({
            'email': user.email,
            **tokens
        })
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Cadastro de usuário",
        description="Cria uma nova conta de usuário.",
        request=RegisterSerializer,
        responses={201: RegisterSerializer, 400: None},
    )
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def register(self, request):
        """Cadastro de novo usuário."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.create_user(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            nome=serializer.validated_data.get('nome'),
            telefone=serializer.validated_data.get('telefone'),
            tipo=serializer.validated_data.get('tipo', User.TipoUsuario.PASSAGEIRO),
        )

        if user.tipo == User.TipoUsuario.PASSAGEIRO:
            empresa = None
            empresa_id = serializer.validated_data.get('empresa_id')
            if empresa_id:
                try:
                    empresa = Company.objects.get(id=empresa_id)
                except Company.DoesNotExist:
                    pass

            Passenger.objects.create(
                user=user,
                cpf=serializer.validated_data.get('cpf', ''),
                empresa=empresa
            )

        tokens = generate_tokens_for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            **tokens
        }, status=status.HTTP_201_CREATED)
