from contextlib import suppress

import magic
from PIL import Image as PilImage
from PIL import UnidentifiedImageError

CONTENT_TYPE_JPG = 'image/jpeg'
CONTENT_TYPE_PNG = 'image/png'
CONTENT_TYPE_PDF = 'application/pdf'

MAGIC_SNIFF_BYTES = 2048

MIME_EXTENSIONS = {
    CONTENT_TYPE_JPG: '.jpg',
    CONTENT_TYPE_PNG: '.png',
    CONTENT_TYPE_PDF: '.pdf',
}


def _rewind(file) -> None:
    if hasattr(file, 'seek') and callable(file.seek):
        file.seek(0)


def get_content_type(file) -> str:
    """Identifica o MIME real do arquivo lendo apenas o cabeçalho (2 KB) e memoizando no objeto."""
    cached = getattr(file, '_detected_mime_type', None)
    if cached:
        return cached

    if hasattr(file, 'temporary_file_path'):
        content_type = magic.from_file(file.temporary_file_path(), mime=True)
    else:
        _rewind(file)
        header = file.read(MAGIC_SNIFF_BYTES)
        content_type = magic.from_buffer(header, mime=True)

    _rewind(file)

    with suppress(AttributeError):
        file._detected_mime_type = content_type

    return content_type


def extension_for_content_type(content_type: str) -> str:
    """Retorna extensão determinística a partir do MIME allowlisted."""
    return MIME_EXTENSIONS.get(content_type, '')


def is_valid_image_file(file) -> bool:
    """Verifica a integridade estrutural da imagem usando Pillow sem carregar os pixels completos."""
    try:
        _rewind(file)
        with PilImage.open(file) as img:
            img.verify()
        return True
    except (UnidentifiedImageError, PilImage.DecompressionBombError, OSError, ValueError):
        return False
    finally:
        _rewind(file)
