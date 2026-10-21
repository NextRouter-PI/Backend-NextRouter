from rest_framework import mixins, parsers, viewsets
from rest_framework.permissions import AllowAny

from uploader.models import Document, Image
from uploader.serializers import DocumentUploadSerializer, ImageUploadSerializer


class CreateViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    Apenas envio de arquivos. O envio é público porque acontece antes do cadastro do usuário
    (foto de perfil, CNH, documentos da empresa). Não há listagem: ela exporia os arquivos e as
    chaves de vínculo (attachment_key) de todos os usuários.
    """

    permission_classes = (AllowAny,)
    parser_classes = (parsers.FormParser, parsers.MultiPartParser)


class DocumentUploadViewSet(CreateViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentUploadSerializer


class ImageUploadViewSet(CreateViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageUploadSerializer
