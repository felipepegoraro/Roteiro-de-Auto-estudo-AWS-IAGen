#!/usr/bin/env bash
# Etapa 4: S3 -> Lambda -> Bedrock -> DynamoDB no Floci. Idempotente: pode rodar quantas vezes quiser.
# Uso: ./etapa4/deploy.sh            (DEFESA=0 ./etapa4/deploy.sh para o prompt original, sem defesa)
set -euo pipefail
export AWS_PROFILE=floci
cd "$(dirname "$0")"

conta=$(aws sts get-caller-identity --query Account --output text)
[ "$conta" = "000000000000" ] || { echo "PARE: conta $conta não é o Floci"; exit 1; }

BUCKET=relatorios-campo TABELA=triagem FUNCAO=triagem ROLE=triagem-lambda
ARN_FUNCAO=arn:aws:lambda:us-east-1:000000000000:function:$FUNCAO

aws s3api head-bucket --bucket $BUCKET 2>/dev/null || aws s3 mb s3://$BUCKET

aws dynamodb describe-table --table-name $TABELA >/dev/null 2>&1 || aws dynamodb create-table --table-name $TABELA \
  --attribute-definitions AttributeName=arquivo,AttributeType=S \
  --key-schema AttributeName=arquivo,KeyType=HASH --billing-mode PAY_PER_REQUEST >/dev/null

aws iam get-role --role-name $ROLE >/dev/null 2>&1 || aws iam create-role --role-name $ROLE \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
# menor privilégio: só ler o bucket, gravar na tabela, chamar o modelo e escrever logs
aws iam put-role-policy --role-name $ROLE --policy-name triagem-minimo --policy-document file://politica_lambda.json

python3 -c "import zipfile; zipfile.ZipFile('funcao.zip','w').write('app.py')"
VARS="Variables={TABELA=$TABELA,DEFESA=${DEFESA:-1}}"
if aws lambda get-function --function-name $FUNCAO >/dev/null 2>&1; then
  aws lambda update-function-code --function-name $FUNCAO --zip-file fileb://funcao.zip >/dev/null
  aws lambda wait function-updated --function-name $FUNCAO 2>/dev/null || sleep 3
  aws lambda update-function-configuration --function-name $FUNCAO --timeout 120 --environment "$VARS" >/dev/null
else
  aws lambda create-function --function-name $FUNCAO --runtime python3.12 \
    --handler app.handler --zip-file fileb://funcao.zip --timeout 120 \
    --role arn:aws:iam::000000000000:role/$ROLE --environment "$VARS" >/dev/null
fi
rm -f funcao.zip

aws s3api put-bucket-notification-configuration --bucket $BUCKET \
  --notification-configuration "{\"LambdaFunctionConfigurations\":[{\"LambdaFunctionArn\":\"$ARN_FUNCAO\",\"Events\":[\"s3:ObjectCreated:*\"]}]}"

echo "ok: envie com  aws s3 cp etapa4/relatorios/relatorio_alta.txt s3://$BUCKET/  e veja com  aws dynamodb scan --table-name $TABELA"
