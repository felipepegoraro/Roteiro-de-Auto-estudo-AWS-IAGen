#!/usr/bin/env bash
# Recria tudo do zero no Floci:  ./deploy.sh   (idempotente)
set -euo pipefail
cd "$(dirname "$0")"
export AWS_PROFILE=floci

IAM_ENFORCEMENT=true docker compose up -d
docker compose exec -T ollama ollama pull "${MODELO_LOCAL:-llama3.2:1b}"
until curl -sf http://localhost:4566/_floci/health >/dev/null; do sleep 2; done

conta=$(aws sts get-caller-identity --query Account --output text)
[ "$conta" = "000000000000" ] || { echo "PARE: conta $conta não é o Floci"; exit 1; }

[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }

./scripts/etapa2.sh      # recursos de partida + teste de menor privilégio
./etapa4/deploy.sh       # S3 -> Lambda -> Bedrock -> DynamoDB
./etapa5/cenario.sh      # ASG + incidente de CPU + alarme -> SNS -> SQS + usuário do agente

echo
echo "Pronto. Demonstração:"
echo "  aws s3 cp etapa4/relatorios/relatorio_alta.txt s3://relatorios-campo/ && sleep 30 && aws dynamodb scan --table-name triagem"
echo "  .venv/bin/python etapa5/agente.py"
