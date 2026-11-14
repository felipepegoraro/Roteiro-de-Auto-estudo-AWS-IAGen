#!/usr/bin/env bash
# Etapa 5: monta o incidente no Floci (ASG + CPU subindo + alarme -> SNS -> SQS) e o usuário IAM do agente.
# Idempotente. Rode com o Floci em IAM_ENFORCEMENT=true:  IAM_ENFORCEMENT=true docker compose up -d
set -euo pipefail
export AWS_PROFILE=floci
cd "$(dirname "$0")"

conta=$(aws sts get-caller-identity --query Account --output text)
[ "$conta" = "000000000000" ] || { echo "PARE: conta $conta não é o Floci"; exit 1; }

ASG=asg-campo LC=lc-campo TOPICO=alerta-cpu-campo FILA=alertas-campo USUARIO=agente-diagnostico LOGS=/agente/diagnostico

# 1) Launch configuration + ASG (min 1, max 4, desejado 1)
aws autoscaling describe-launch-configurations --launch-configuration-names $LC --query 'LaunchConfigurations[0]' --output text | grep -q $LC ||
  aws autoscaling create-launch-configuration --launch-configuration-name $LC --image-id ami-0abcdef1234567890 --instance-type t3.micro
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names $ASG --query 'AutoScalingGroups[0]' --output text | grep -q $ASG ||
  aws autoscaling create-auto-scaling-group --auto-scaling-group-name $ASG --launch-configuration-name $LC \
    --min-size 1 --max-size 4 --desired-capacity 1 --availability-zones us-east-1a

# 2) SNS -> SQS (create-* são idempotentes na API)
TOPICO_ARN=$(aws sns create-topic --name $TOPICO --query TopicArn --output text)
FILA_URL=$(aws sqs create-queue --queue-name $FILA --query QueueUrl --output text)
FILA_ARN=$(aws sqs get-queue-attributes --queue-url "$FILA_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)
aws sqs set-queue-attributes --queue-url "$FILA_URL" --attributes "{\"Policy\":\"{\\\"Version\\\":\\\"2012-10-17\\\",\\\"Statement\\\":[{\\\"Effect\\\":\\\"Allow\\\",\\\"Principal\\\":{\\\"Service\\\":\\\"sns.amazonaws.com\\\"},\\\"Action\\\":\\\"sqs:SendMessage\\\",\\\"Resource\\\":\\\"$FILA_ARN\\\",\\\"Condition\\\":{\\\"ArnEquals\\\":{\\\"aws:SourceArn\\\":\\\"$TOPICO_ARN\\\"}}}]}\"}"
aws sns list-subscriptions-by-topic --topic-arn "$TOPICO_ARN" --query 'Subscriptions[].Endpoint' --output text | grep -q "$FILA_ARN" ||
  aws sns subscribe --topic-arn "$TOPICO_ARN" --protocol sqs --notification-endpoint "$FILA_ARN" >/dev/null

# 3) Alarme: média de CPU > 80% em 2 períodos de 60 s -> SNS
aws cloudwatch put-metric-alarm --alarm-name cpu-alta-asg-campo --namespace AWS/EC2 --metric-name CPUUtilization \
  --dimensions Name=AutoScalingGroupName,Value=$ASG --statistic Average --period 60 --evaluation-periods 2 \
  --threshold 80 --comparison-operator GreaterThanThreshold --alarm-actions "$TOPICO_ARN"

# 4) Incidente simulado: CPU sobe de 30% a 95% nos últimos 10 minutos (o Floci não gera métrica de EC2 sozinho)
# Só publica se não houver pontos recentes: republicar sobrepõe minutos e dilui a média (visto na 1ª execução)
recentes=$(aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization \
  --dimensions Name=AutoScalingGroupName,Value=$ASG --start-time "$(date -u -d '-10 min' +%FT%TZ)" \
  --end-time "$(date -u +%FT%TZ)" --period 60 --statistics Average --query 'length(Datapoints)')
if [ "$recentes" = "0" ]; then
  i=9
  for cpu in 30 35 42 50 61 70 79 86 91 95; do
    ts=$(date -u -d "-$i min" +%Y-%m-%dT%H:%M:%SZ)
    aws cloudwatch put-metric-data --namespace AWS/EC2 --metric-name CPUUtilization --unit Percent \
      --dimensions AutoScalingGroupName=$ASG --value $cpu --timestamp "$ts"
    i=$((i - 1))
  done
else
  echo "métricas recentes já existem ($recentes pontos): incidente não republicado (aguarde 10 min para um novo)"
fi

# 5) Log group de auditoria + usuário próprio do agente (menor privilégio)
aws logs create-log-group --log-group-name $LOGS 2>/dev/null || true
aws iam get-user --user-name $USUARIO >/dev/null 2>&1 || aws iam create-user --user-name $USUARIO >/dev/null
# politica_iam.json tem os ARNs da AWS real. LIMITAÇÕES DO FLOCI (testadas, ver evidencias/etapa5/):
#  - autoscaling: o IAM ainda não lê o recurso (ARN do ASG no Floci é autoScalingGroup:<nome>, sem o <id> da AWS);
#  - logs: nenhum ARN específico casou no PutLogEvents, nem arn:aws:logs:us-east-1:000000000000:*.
# Nesses dois Sids, e só neles, o Floci recebe Resource "*". As AÇÕES continuam mínimas, e o agente.py compensa
# aceitando só asg-campo (1..4) e gravando só em /agente/diagnostico.
TMP_POL=$(mktemp)
python3 -c "
import json; d = json.load(open('politica_iam.json'))
for s in d['Statement']:
    if s['Sid'] in ('EscalarSoAsgCampo', 'LogDeAuditoria'): s['Resource'] = '*'
print(json.dumps(d))" > "$TMP_POL"
aws iam put-user-policy --user-name $USUARIO --policy-name agente-minimo --policy-document "file://$TMP_POL"
rm -f "$TMP_POL"
# credencial do agente fica fora do git (.gitignore); no Floci é fictícia, mas o hábito é o que vale
[ -s .credenciais_agente.json ] || aws iam create-access-key --user-name $USUARIO --query AccessKey > .credenciais_agente.json

for _ in $(seq 1 12); do  # o alarme é avaliado periodicamente; espera até ~60 s
  [ "$(aws cloudwatch describe-alarms --alarm-names cpu-alta-asg-campo --query 'MetricAlarms[0].StateValue' --output text)" = ALARM ] && break
  sleep 5
done
echo "ok: cenário montado. Estado do alarme:"
aws cloudwatch describe-alarms --alarm-names cpu-alta-asg-campo --query 'MetricAlarms[0].[StateValue,StateReason]' --output text
