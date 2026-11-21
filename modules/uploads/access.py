"""Registro de verificadores de acesso a documentos privados sem acoplar `uploads` aos módulos de negócio."""

from collections.abc import Callable

from modules.uploads.models import Document

DocumentAccessChecker = Callable[[object, Document], bool]
_CHECKERS: list[DocumentAccessChecker] = []


def register_document_access_checker(checker: DocumentAccessChecker) -> None:
    if checker not in _CHECKERS:
        _CHECKERS.append(checker)


def can_access_document(user, document: Document) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return any(checker(user, document) for checker in _CHECKERS)
