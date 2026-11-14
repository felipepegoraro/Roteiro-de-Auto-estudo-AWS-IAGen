# GenAI na Automação de Serviços AWS (ambiente Floci)

Grupo: **Felipe Pegoraro, Thiago Siena, Pedro Borges**

Tema do projeto integrador: agronegócio (triagem de relatórios de inspeção de lavoura + agente de diagnóstico de Auto Scaling).

## Subir o ambiente

```bash
docker compose up -d
docker compose exec ollama ollama pull llama3.2:1b
export AWS_PROFILE=floci            # perfil em ~/.aws/config, endpoint http://localhost:4566
aws sts get-caller-identity         # TEM que mostrar 000000000000; se não, pare
```

Perfil `~/.aws/config`:

```ini
[profile floci]
region = us-east-1
endpoint_url = http://localhost:4566
aws_access_key_id = test
aws_secret_access_key = test
```

Variáveis do compose: `MODELO_LOCAL` (padrão `llama3.2:1b`) e `IAM_ENFORCEMENT` (padrão `false`; use `IAM_ENFORCEMENT=true docker compose up -d` nas Etapas 2 e 5).

## Etapas

| Etapa | Pasta | Status |
|---|---|---|
| 0 Ambiente | `docker-compose.yml`, `evidencias/etapa0/` | ok |

## Na AWS real

- Sem `endpoint_url`: o perfil aponta para a conta real e cada token do Bedrock é cobrado.
