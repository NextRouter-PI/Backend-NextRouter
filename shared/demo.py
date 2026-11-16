"""Identificadores sintéticos para fixtures; nunca dados de pessoas reais."""

from django.core.files.base import ContentFile


def placeholder_pdf(description):
    text = description.replace('(', '').replace(')', '')[:60]
    return ContentFile(
        f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Resources << >> /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 80 >>
stream
BT /F1 18 Tf 20 100 Td ({text}) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
trailer
<< /Size 5 /Root 1 0 R >>
startxref
0
%%EOF
""".encode(),
        name='documento.pdf',
    )


def make_cpf(base9):
    digits = [int(value) for value in base9]
    for size in (10, 11):
        remainder = sum(value * weight for value, weight in zip(digits, range(size, 1, -1), strict=True)) * 10 % 11
        digits.append(0 if remainder == 10 else remainder)
    return ''.join(map(str, digits))


def make_cnpj(base12):
    digits = [int(value) for value in base12]
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        remainder = sum(value * weight for value, weight in zip(digits, weights, strict=True)) % 11
        digits.append(0 if remainder < 2 else 11 - remainder)
    return ''.join(map(str, digits))
