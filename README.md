# Instruções para teste

Prepare o ambiente de desenvolvimento:
```bash
pdm run predev
```
Carregue os dados do JSON:
```bash
pdm run loaddata
```
Crie as migrações do banco:
```bash
pdm premigrate
```
Aplique as migrações do banco:
```bash
pdm run migrate
```
Inicie o servidor:
```bash
pdm run dev
```
Acesse os endpoints em:
<u>http://127.0.0.1:8000/api/doc/</u>
