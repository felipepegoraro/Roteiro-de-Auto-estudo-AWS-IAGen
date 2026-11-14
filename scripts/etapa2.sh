#!/usr/bin/env bash
# Etapa 2: recursos de partida + teste de menor privilégio do tecnico-campo (get-object passa, put-object falha).
# Idempotente. Precisa do Floci com IAM_ENFORCEMENT=true para o teste de permissão valer.
set -euo pipefail
export AWS_PROFILE=floci
cd "$(dirname "$0")"

conta=$(aws sts get-caller-identity --query Account --output text)
[ "$conta" = "000000000000" ] || { echo "PARE: conta $conta não é o Floci"; exit 1; }

# recursos de partida (quadro do roteiro)
for b in relatorios imagens-drone; do aws s3api head-bucket --bucket $b 2>/dev/null || aws s3 mb s3://$b; done
echo "Inspeção talhão 12: sem pragas" | aws s3 cp - s3://relatorios/inspecao-001.txt
aws dynamodb describe-table --table-name sensores >/dev/null 2>&1 || aws dynamodb create-table --table-name sensores \
  --attribute-definitions AttributeName=id,AttributeType=S --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST >/dev/null
aws iam get-user --user-name tecnico-campo >/dev/null 2>&1 || aws iam create-user --user-name tecnico-campo >/dev/null

# menor privilégio: só ler objetos do bucket relatorios
aws iam put-user-policy --user-name tecnico-campo --policy-name so-ler-relatorios --policy-document '{
  "Version": "2012-10-17",
  "Statement": [{"Sid": "LerRelatorios", "Effect": "Allow", "Action": "s3:GetObject",
                 "Resource": "arn:aws:s3:::relatorios/*"}]}'
[ -s .credenciais_tecnico.json ] || aws iam create-access-key --user-name tecnico-campo --query AccessKey > .credenciais_tecnico.json

# teste com a chave do tecnico-campo (sem o perfil admin, endpoint explícito)
tec() {
  env -u AWS_PROFILE AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_DEFAULT_REGION=us-east-1 \
    AWS_ENDPOINT_URL=http://localhost:4566 \
    AWS_ACCESS_KEY_ID=$(python3 -c "import json;print(json.load(open('.credenciais_tecnico.json'))['AccessKeyId'])") \
    AWS_SECRET_ACCESS_KEY=$(python3 -c "import json;print(json.load(open('.credenciais_tecnico.json'))['SecretAccessKey'])") \
    aws "$@"
}
echo "== identidade:"; tec sts get-caller-identity --query Arn --output text
echo "== get-object relatorios/inspecao-001.txt (deve PASSAR):"
tec s3api get-object --bucket relatorios --key inspecao-001.txt /dev/stdout --query ContentLength --output text \
  && echo "PASSOU" || echo "FALHOU (inesperado)"
echo "== put-object relatorios/invasor.txt (deve FALHAR):"
echo x | tec s3 cp - s3://relatorios/invasor.txt 2>&1 && echo "PASSOU (inesperado!)" || echo "FALHOU como esperado"
echo "== listar imagens-drone (fora do escopo, deve FALHAR):"
tec s3 ls s3://imagens-drone 2>&1 && echo "PASSOU (inesperado!)" || echo "FALHOU como esperado"
