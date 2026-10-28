import argparse
import sys
from pathlib import Path

import yaml

HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete'}


def load_schema(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def _resolve_schema(schema_node: dict, components: dict) -> dict:
    if not isinstance(schema_node, dict):
        return {}
    if '$ref' in schema_node:
        ref_name = schema_node['$ref'].split('/')[-1]
        return _resolve_schema(components.get(ref_name, {}), components)
    if 'oneOf' in schema_node:
        merged_props: dict = {}
        disc = schema_node.get('discriminator', {}).get('propertyName')
        if disc:
            merged_props[disc] = {'type': 'string'}
        for sub in schema_node['oneOf']:
            resolved = _resolve_schema(sub, components)
            merged_props.update(resolved.get('properties') or {})
        return {'type': 'object', 'properties': merged_props}
    if 'allOf' in schema_node:
        merged_props = {}
        for sub in schema_node['allOf']:
            resolved = _resolve_schema(sub, components)
            merged_props.update(resolved.get('properties') or {})
        return {'type': 'object', 'properties': merged_props}
    return schema_node


def _validate_example_value(
    example_val,
    schema_node: dict,
    components: dict,
    context_label: str,
    issues: list[str],
    is_error_response: bool = False,
) -> None:
    resolved = _resolve_schema(schema_node, components)
    if not resolved:
        return
    if resolved.get('type') == 'array' or 'items' in resolved:
        if not isinstance(example_val, list):
            issues.append(f'[EXEMPLO INVÁLIDO - ESPERADO LISTA] {context_label}')
            return
        for item in example_val:
            _validate_example_value(
                item, resolved.get('items', {}), components, context_label, issues, is_error_response
            )
        return
    props = resolved.get('properties')
    if props and isinstance(example_val, dict) and not is_error_response:
        unknown_keys = set(example_val.keys()) - set(props.keys())
        if unknown_keys:
            issues.append(f'[EXEMPLO COM CAMPOS INEXISTENTES NO SERIALIZER] {context_label}: {sorted(unknown_keys)}')


def audit_schema(schema: dict) -> tuple[dict, list[str]]:
    paths = schema.get('paths', {})
    components = schema.get('components', {}).get('schemas', {})

    total_ops = 0
    with_summary = 0
    with_description = 0
    with_tags = 0
    with_error_resp = 0
    with_examples = 0
    validated_examples = 0

    issues: list[str] = []

    for route, path_item in sorted(paths.items()):
        for method, op in sorted(path_item.items()):
            if method.lower() not in HTTP_METHODS or not isinstance(op, dict):
                continue
            total_ops += 1
            op_label = f'{method.upper()} {route}'

            summary = (op.get('summary') or '').strip()
            description = (op.get('description') or '').strip()
            tags = op.get('tags') or []
            responses = op.get('responses') or {}

            if summary:
                with_summary += 1
            else:
                issues.append(f'[OPERAÇÃO SEM SUMMARY] {op_label}')

            if description:
                with_description += 1
            else:
                issues.append(f'[OPERAÇÃO SEM DESCRIPTION] {op_label}')

            if tags:
                with_tags += 1
            else:
                issues.append(f'[OPERAÇÃO SEM TAGS] {op_label}')

            has_4xx = any(str(code).startswith('4') for code in responses)
            if has_4xx:
                with_error_resp += 1
            else:
                issues.append(f'[OPERAÇÃO SEM RESPOSTA DE ERRO 4XX] {op_label}')

            has_example = False
            req_body = op.get('requestBody', {}).get('content', {})
            for media in req_body.values():
                media_schema = media.get('schema') or {}
                if media.get('examples') or media.get('example'):
                    has_example = True
                for ex_name, ex_obj in (media.get('examples') or {}).items():
                    if isinstance(ex_obj, dict) and 'value' in ex_obj:
                        validated_examples += 1
                        _validate_example_value(
                            ex_obj['value'],
                            media_schema,
                            components,
                            f'{op_label} request ({ex_name})',
                            issues,
                        )
            for code, resp in responses.items():
                is_err = str(code).startswith(('4', '5'))
                for media in (resp.get('content') or {}).values():
                    media_schema = media.get('schema') or {}
                    if media.get('examples') or media.get('example'):
                        has_example = True
                    for ex_name, ex_obj in (media.get('examples') or {}).items():
                        if isinstance(ex_obj, dict) and 'value' in ex_obj:
                            validated_examples += 1
                            _validate_example_value(
                                ex_obj['value'],
                                media_schema,
                                components,
                                f'{op_label} response {code} ({ex_name})',
                                issues,
                                is_error_response=is_err,
                            )
            if has_example:
                with_examples += 1
            else:
                issues.append(f'[OPERAÇÃO SEM EXEMPLOS] {op_label}')

    total_fields = 0
    fields_with_desc = 0
    for comp_name, comp_schema in sorted(components.items()):
        if not isinstance(comp_schema, dict):
            continue
        props = comp_schema.get('properties') or {}
        for prop_name, prop_schema in sorted(props.items()):
            if not isinstance(prop_schema, dict):
                continue
            total_fields += 1
            desc = (prop_schema.get('description') or '').strip()
            if desc or '$ref' in prop_schema or 'allOf' in prop_schema:
                fields_with_desc += 1
            else:
                issues.append(f'[CAMPO SEM DESCRIPTION] {comp_name}.{prop_name}')

    stats = {
        'total_ops': total_ops,
        'with_summary': with_summary,
        'with_description': with_description,
        'with_tags': with_tags,
        'with_error_resp': with_error_resp,
        'with_examples': with_examples,
        'validated_examples': validated_examples,
        'total_fields': total_fields,
        'fields_with_desc': fields_with_desc,
        'issues_count': len(issues),
    }
    return stats, issues


def extract_structure(schema: dict, ignore_meta_schema: bool = False) -> dict[str, list[str]]:
    structure: dict[str, list[str]] = {}
    for route, path_item in sorted(schema.get('paths', {}).items()):
        if ignore_meta_schema and route == '/api/schema/':
            continue
        methods = sorted(m.upper() for m in path_item if m.lower() in HTTP_METHODS)
        structure[route] = methods
    return structure


def compare_schemas(before: dict, after: dict) -> list[str]:
    diffs: list[str] = []
    before_routes = extract_structure(before, ignore_meta_schema=True)
    after_routes = extract_structure(after, ignore_meta_schema=True)

    for route in sorted(set(before_routes) | set(after_routes)):
        if route not in before_routes:
            diffs.append(f'Rota adicionada: {route} ({after_routes[route]})')
        elif route not in after_routes:
            diffs.append(f'Rota removida: {route} ({before_routes[route]})')
        elif before_routes[route] != after_routes[route]:
            diffs.append(f'Métodos alterados em {route}: antes={before_routes[route]} depois={after_routes[route]}')

    return diffs


def main() -> int:
    parser = argparse.ArgumentParser(description='Audita a completude do schema OpenAPI do NextRouter.')
    parser.add_argument('schema_file', type=Path, help='Caminho para o arquivo YAML do schema.')
    parser.add_argument('--compare', type=Path, help='Arquivo YAML anterior para comparação estrutural.')
    parser.add_argument('--strict', action='store_true', help='Retorna código != 0 se houver pendências.')
    args = parser.parse_args()

    schema = load_schema(args.schema_file)
    stats, issues = audit_schema(schema)

    print('=== RESUMO DA AUDITORIA DO SCHEMA ===')
    print(f'Total de operações:             {stats["total_ops"]}')
    print(f'Com summary:                    {stats["with_summary"]}/{stats["total_ops"]}')
    print(f'Com description:                {stats["with_description"]}/{stats["total_ops"]}')
    print(f'Com tags:                       {stats["with_tags"]}/{stats["total_ops"]}')
    print(f'Com respostas de erro (4xx):    {stats["with_error_resp"]}/{stats["total_ops"]}')
    print(f'Com exemplos (OpenApiExample):  {stats["with_examples"]}/{stats["total_ops"]}')
    print(f'Exemplos validados (schema):    {stats["validated_examples"]}')
    print(f'Campos com description/$ref:    {stats["fields_with_desc"]}/{stats["total_fields"]}')
    print(f'Total de pendências:            {stats["issues_count"]}')

    if args.compare:
        before = load_schema(args.compare)
        diffs = compare_schemas(before, schema)
        print('\n=== COMPARAÇÃO ESTRUTURAL (ROTAS E MÉTODOS) ===')
        if not diffs:
            print('Nenhuma rota ou método HTTP foi alterado (100% compatível).')
        else:
            for d in diffs:
                print(f'  - {d}')

    if issues:
        print('\n=== LISTA DE PENDÊNCIAS ===')
        for item in issues[:50]:
            print(f'  - {item}')
        if len(issues) > 50:
            print(f'  ... e mais {len(issues) - 50} pendências.')

    if args.strict and issues:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
