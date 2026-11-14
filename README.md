# GenAI na Automação de Serviços AWS (ambiente Floci)

Grupo: **Felipe Pegoraro, Thiago Siena, Pedro Borges**

Tema do projeto integrador: agronegócio (triagem de relatórios de inspeção de lavoura + agente de diagnóstico de Auto Scaling).

## Tudo do zero em 2 comandos

```bash
docker compose up -d
./deploy.sh        # idempotente: modelo, venv, Etapas 2, 4 e 5 (IAM ligado)
```

Documentos: `docs/arquitetura.md` (diagrama), `docs/relatorio_etapa6.md` (custo, riscos, recomendação), `docs/apresentacao.md`, `DIARIO_DE_PROMPTS.md`, `iac/problemas.md`.

## Subir o ambiente (passo a passo)

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
| 4 S3 → Lambda → Bedrock → DynamoDB | `etapa4/`, `evidencias/etapa4/` | ok |
| 1 Fundamentos (rascunho) | `docs/glossario.md`, `docs/mapa_servicos.md` | rascunho |
| 2 Assistentes / menor privilégio | `scripts/etapa2.sh`, `scripts/inventario.py`, `evidencias/etapa2/` | ok |
| 3 IaC (CloudFormation) | `iac/`, `evidencias/etapa3/` | ok |
| 5 Agente de diagnóstico | `etapa5/`, `evidencias/etapa5/` | ok (execução com aprovação: ver abaixo) |
| 6 Custo, segurança, TI Verde | `scripts/custo.py`, `docs/relatorio_etapa6.md` | ok |

### Etapa 4 em 3 comandos

```bash
./etapa4/deploy.sh                                          # idempotente; DEFESA=0 para o prompt original
aws s3 cp etapa4/relatorios/relatorio_alta.txt s3://relatorios-campo/
aws dynamodb scan --table-name triagem                      # ~10-60 s depois
python3 etapa4/test_app.py                                  # teste local: JSON inválido e injeção
```

Resultado medido (llama3.2:1b): baixa→`baixa`, alta→`alta`, injeção→`revisao_humana` (com defesa), média oscilou entre `baixa`/`alta` (limite do modelo de 1B).

### Etapa 3

```bash
uvx cfn-lint iac/vpc.yaml
aws cloudformation deploy --template-file iac/vpc.yaml --stack-name lab-ia
aws cloudformation describe-stack-resources --stack-name lab-ia
aws cloudformation delete-stack --stack-name lab-ia
```

Problemas encontrados no template gerado e correções: `iac/problemas.md`.

### Etapa 5

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # boto3 com Converse (>= 1.35)
IAM_ENFORCEMENT=true docker compose up -d
./etapa5/cenario.sh                    # ASG, CPU 30→95%, alarme → SNS → SQS, usuário IAM do agente
.venv/bin/python etapa5/agente.py      # pede aprovação [s/N] antes de ajustar_capacidade
aws logs tail /agente/diagnostico      # auditoria de cada chamada de ferramenta
```

### Limitações do Floci encontradas

- Estado em memória por padrão: sem `FLOCI_STORAGE_MODE=persistent`, tudo some no restart.
- IAM não avalia o **recurso** em chamadas de `autoscaling` e de `logs`: só `Resource: "*"` funciona. O `cenario.sh` alarga só esses dois Sids no Floci; `etapa5/politica_iam.json` tem os ARNs da AWS real.
- Tool use em CPU com modelo de 1B leva 30–40 s por chamada: timeouts aumentados (proxy 300 s, boto3 300 s).
- Nenhum modelo local testado (llama3.2:1b, qwen2.5:1.5b, qwen2.5:3b) chamou a ferramenta de escrita: quando a CPU está sustentada (fato calculado no código), o agente propõe +1 de capacidade, rotulado como proposta do código, que passa pela aprovação `[s/N]`. Teste do laço: `.venv/bin/python etapa5/test_agente.py`.

## Na AWS real

- Sem `endpoint_url`: o perfil aponta para a conta real e cada token do Bedrock é cobrado.
- Etapa 5: a política do agente usa os ARNs de `politica_iam.json` sem alteração, as métricas de CPU vêm do EC2 automaticamente e o CloudTrail registra cada `SetDesiredCapacity` com a identidade de quem chamou.
- Etapa 4: o mesmo `app.py` roda sem mudança; muda o `modelId` (modelo habilitado na conta) e a role passa a ser avaliada de verdade (`politica_lambda.json` já restringe `bedrock:InvokeModel` ao modelo).
