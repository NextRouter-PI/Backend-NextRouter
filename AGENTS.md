# NextRouter — entrada para agentes no backend

O contexto e as regras completas foram centralizados um nível acima, em
[CONTEXTO_BACKEND.md](../CONTEXTO_BACKEND.md). Leia também o
[índice do workspace](../AGENTS.md), o [planejamento de domínio](../PLANEJAMENTO.md)
e, para tarefas integradas, o [plano de implementação](../PLANO_IMPLEMENTACAO.md).
Se este for um checkout isolado sem os documentos centrais, peça acesso a eles
antes de alterar regras do produto ou o contrato de integração.

## Restrições que valem também em checkout isolado

- Não consultar ou migrar o banco habitual para validar alterações. Confirme
  autorização antes de criar/aplicar migrations, alterar settings/dependências ou
  executar operações destrutivas. Não reescreva migrations aplicadas nem use `--fake`
  para contornar a incompatibilidade do legado.
- Use ambiente descartável, dados fictícios e integrações externas isoladas.
  Não exponha segredos, documentos, endereços ou coordenadas; não faça push/merge
  ou deploy sem pedido.
- Preserve same-origin, cookies HttpOnly, CSRF, origem WS, autorização por
  empresa/participação e documentos privados. Não reative recursos retirados ou
  contorne serviços transacionais com escritas genéricas. `html-template-test/`
  é apenas para DEBUG e nunca deve entrar no artefato de produção.
- O código comprova o comportamento atual; builds fictícios ou testes do cliente
  HTML não comprovam integração Vue. Em mudanças documentais, confira links e
  `git diff --check`. Registre evidências e limites nos documentos centrais.
- Não alterar migrações a menos se for explícitamente pedido.