from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, parsers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated

from modules.organizations.models import Company, Driver
from modules.uploads.api.serializers import DocumentUploadSerializer, ImageUploadSerializer
from modules.uploads.models import Document, Image
from shared.openapi import RESP_400_VALIDATION, RESP_401_UNAUTHORIZED, RESP_404_NOT_FOUND


class CreateViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Apenas envio de arquivos. O envio é público porque acontece antes do cadastro do usuário
    (foto de perfil, CNH, documentos da empresa). Não há listagem: ela exporia os arquivos e as
    chaves de vínculo (attachment_key) de todos os usuários.
    """

    permission_classes = (AllowAny,)
    parser_classes = (parsers.FormParser, parsers.MultiPartParser)


@extend_schema_view(
    create=extend_schema(
        tags=['Arquivos'],
        summary='Envie documento',
        description='Upload público antes do cadastro; aceita PDF até 10 MB. Chave de vínculo não autoriza download.',
        responses={201: DocumentUploadSerializer, 400: RESP_400_VALIDATION},
    )
)
class DocumentUploadViewSet(CreateViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentUploadSerializer

    @extend_schema(
        tags=['Arquivos'],
        summary='Baixe documento próprio',
        description=(
            'Somente titular do documento (empresa/motorista) ou administrador. Documento de terceiros retorna 404.'
        ),
        responses={(200, 'application/pdf'): bytes, 401: RESP_401_UNAUTHORIZED, 404: RESP_404_NOT_FOUND},
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated], url_path='download')
    def download(self, request, pk=None):
        document = get_object_or_404(Document, attachment_key=pk)
        user = request.user
        allowed = user.is_staff or user.is_superuser
        if not allowed:
            allowed = (
                Company.objects
                .filter(user=user)
                .filter(
                    Q(articles_of_association_document=document)
                    | Q(state_operating_license_document=document)
                    | Q(certificate_of_good_stading_document=document)
                )
                .exists()
                or Driver.objects.filter(user=user, cnh=document).exists()
            )
        if not allowed:
            raise Http404
        return FileResponse(document.file.open('rb'), content_type='application/pdf')


@extend_schema_view(
    create=extend_schema(
        tags=['Arquivos'],
        summary='Envie imagem',
        description='Upload público antes do cadastro; aceita JPG ou PNG até 5 MB.',
        responses={201: ImageUploadSerializer, 400: RESP_400_VALIDATION},
    )
)
class ImageUploadViewSet(CreateViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageUploadSerializer
