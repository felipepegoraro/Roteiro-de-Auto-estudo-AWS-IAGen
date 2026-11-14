"""Etapa 5: agente de diagnóstico do asg-campo (Bedrock Converse + tool use).
Usa as credenciais do usuário IAM próprio (agente-diagnostico), nunca as do perfil admin.
Uso: python3 etapa5/agente.py ["pergunta"]"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

AQUI = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = os.environ.get("FLOCI_URL", "http://localhost:4566")
MODELO = "amazon.nova-micro-v1:0"
ASG_PERMITIDO, CAP_MIN, CAP_MAX = "asg-campo", 1, 4
LOG_GROUP = "/agente/diagnostico"
MAX_ITERACOES = 6

chave = json.load(open(os.path.join(AQUI, ".credenciais_agente.json")))  # gerado por cenario.sh
sessao = boto3.Session(aws_access_key_id=chave["AccessKeyId"], aws_secret_access_key=chave["SecretAccessKey"],
                       region_name="us-east-1")
# modelo local em CPU leva ~40-90 s com ferramentas: o read_timeout padrão (60 s) estoura; sem retry p/ não repetir inferência
CFG = Config(read_timeout=300, retries={"max_attempts": 1})
cli = lambda svc: sessao.client(svc, endpoint_url=ENDPOINT, config=CFG)  # noqa: E731  endpoint explícito: nunca cai na AWS real
cw, asg, logs, bedrock = cli("cloudwatch"), cli("autoscaling"), cli("logs"), cli("bedrock-runtime")
STREAM = datetime.now().strftime("execucao-%Y%m%d-%H%M%S")


def log(evento):
    """Auditoria: cada chamada de ferramenta vai para o CloudWatch Logs."""
    evento = json.dumps(evento, ensure_ascii=False, default=str)
    print(f"  [log] {evento}")
    logs.put_log_events(logGroupName=LOG_GROUP, logStreamName=STREAM,
                        logEvents=[{"timestamp": int(time.time() * 1000), "message": evento}])


def ler_metricas(nome_asg=ASG_PERMITIDO, minutos=15):
    fim = datetime.now(timezone.utc)
    r = cw.get_metric_statistics(Namespace="AWS/EC2", MetricName="CPUUtilization",
                                 Dimensions=[{"Name": "AutoScalingGroupName", "Value": nome_asg}],
                                 StartTime=fim - timedelta(minutes=int(minutos)), EndTime=fim,
                                 Period=60, Statistics=["Average", "Maximum"])
    pontos = sorted(r["Datapoints"], key=lambda p: p["Timestamp"])
    if not pontos:  # 1ª execução: o modelo passou o nome do ALARME como ASG e concluiu sem dados
        return {"quantidade_de_pontos": 0,
                "erro": f"sem métricas para '{nome_asg}'. O grupo de Auto Scaling se chama '{ASG_PERMITIDO}'."}
    return {"quantidade_de_pontos": len(pontos),
            "pontos": [{"hora": p["Timestamp"].strftime("%H:%M"), "media": round(p["Average"], 1),
                        "maximo": round(p["Maximum"], 1)} for p in pontos]}


def descrever_asg(nome_asg=ASG_PERMITIDO):
    g = asg.describe_auto_scaling_groups(AutoScalingGroupNames=[nome_asg])["AutoScalingGroups"]
    if not g:
        return {"erro": f"ASG {nome_asg} não encontrado"}
    g = g[0]
    return {"nome": g["AutoScalingGroupName"], "minimo": g["MinSize"], "maximo": g["MaxSize"],
            "desejado": g["DesiredCapacity"], "instancias": len(g.get("Instances", []))}


def listar_atividades(nome_asg=ASG_PERMITIDO):
    a = asg.describe_scaling_activities(AutoScalingGroupName=nome_asg, MaxRecords=5)["Activities"]
    return {"atividades": [{"descricao": x.get("Description"), "status": x.get("StatusCode"),
                            "inicio": str(x.get("StartTime"))} for x in a]}


def ajustar_capacidade(nome_asg, capacidade):
    # trava no código, além do IAM (o Floci não restringe o recurso do autoscaling; ver cenario.sh)
    capacidade = int(capacidade)
    if nome_asg != ASG_PERMITIDO or not CAP_MIN <= capacidade <= CAP_MAX:
        return {"erro": f"só é permitido ajustar {ASG_PERMITIDO} entre {CAP_MIN} e {CAP_MAX}"}
    asg.set_desired_capacity(AutoScalingGroupName=nome_asg, DesiredCapacity=capacidade, HonorCooldown=False)
    return {"ok": True, "novo_desejado": capacidade}


FUNCOES = {f.__name__: f for f in (ler_metricas, descrever_asg, listar_atividades, ajustar_capacidade)}
P_ASG = {"nome_asg": {"type": "string", "description": "nome do grupo de Auto Scaling, ex.: asg-campo"}}


def spec(nome, descricao, props, obrig=()):
    return {"toolSpec": {"name": nome, "description": descricao, "inputSchema": {"json": {
        "type": "object", "properties": props, "required": list(obrig)}}}}


FERRAMENTAS = [
    spec("ler_metricas", "Lê a CPU (média e máxima por minuto) do ASG nos últimos N minutos.",
         {**P_ASG, "minutos": {"type": "integer", "description": "janela em minutos (padrão 15)"}}),
    spec("descrever_asg", "Mostra mínimo, máximo, capacidade desejada e instâncias do ASG.", P_ASG),
    spec("listar_atividades", "Lista as últimas atividades de escalonamento do ASG.", P_ASG),
    spec("ajustar_capacidade", "ESCRITA: muda a capacidade desejada do ASG. Exige aprovação humana.",
         {**P_ASG, "capacidade": {"type": "integer", "description": "nova capacidade desejada (1 a 4)"}},
         ["nome_asg", "capacidade"]),
]
SISTEMA = (
    "Você é um agente de diagnóstico de infraestrutura de uma aplicação de monitoramento de lavouras na AWS. "
    "Use as ferramentas para investigar antes de concluir: leia as métricas de CPU (vários pontos, não um só), "
    "veja o estado do ASG e as atividades recentes. Só proponha ajustar_capacidade se a CPU estiver alta de forma "
    "sustentada em vários minutos. Responda em português com três itens: O que aconteceu; Causa provável; "
    "Ação recomendada."
)


def executar(nome, entrada):
    if nome not in FUNCOES:
        return {"erro": f"ferramenta desconhecida: {nome}"}
    try:
        return json.loads(json.dumps(FUNCOES[nome](**entrada), default=str))
    except Exception as e:  # erro de API/argumento vira resultado para o modelo, não derruba o agente
        return {"erro": f"{type(e).__name__}: {e}"}


def main():
    conta = sessao.client("sts", endpoint_url=ENDPOINT).get_caller_identity()
    assert conta["Account"] == "000000000000", f"PARE: conta {conta['Account']} não é o Floci"
    print(f"Identidade: {conta['Arn']}\nLog de auditoria: {LOG_GROUP} / {STREAM}\n")
    logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=STREAM)
    pergunta = sys.argv[1] if len(sys.argv) > 1 else (
        "O alarme de CPU (nome do alarme: cpu-alta-asg-campo) disparou. O grupo de Auto Scaling se chama asg-campo. "
        "Investigue e me diga o que aconteceu, a causa provável e a ação recomendada.")
    msgs = [{"role": "user", "content": [{"text": pergunta}]}]
    log({"evento": "inicio", "pergunta": pergunta, "identidade": conta["Arn"]})

    pontos_lidos = 0  # guarda: sem métricas reais, o diagnóstico não é aceito
    for iteracao in range(1, MAX_ITERACOES + 1):
        resp = bedrock.converse(modelId=MODELO, system=[{"text": SISTEMA}], messages=msgs,
                                toolConfig={"tools": FERRAMENTAS}, inferenceConfig={"temperature": 0, "maxTokens": 400})
        msg = resp["output"]["message"]
        msgs.append(msg)
        if resp["stopReason"] != "tool_use" and pontos_lidos < 3 and iteracao < MAX_ITERACOES:
            aviso = (f"Diagnóstico recusado: você ainda não leu métricas reais ({pontos_lidos} pontos). "
                     f"Chame ler_metricas com nome_asg='{ASG_PERMITIDO}' antes de concluir.")
            print(f"\n[iteração {iteracao}] {aviso}")
            log({"evento": "diagnostico_recusado", "iteracao": iteracao, "pontos_lidos": pontos_lidos})
            msgs.append({"role": "user", "content": [{"text": aviso}]})
            continue
        if resp["stopReason"] != "tool_use":
            texto = "\n".join(b["text"] for b in msg["content"] if "text" in b)
            print(f"\n=== Diagnóstico (iteração {iteracao}) ===\n{texto}")
            log({"evento": "fim", "iteracao": iteracao, "resposta": texto})
            return
        resultados = []
        for bloco in msg["content"]:
            if "toolUse" not in bloco:
                continue
            uso = bloco["toolUse"]
            nome, entrada, aprovado = uso["name"], uso.get("input") or {}, None
            print(f"\n[iteração {iteracao}] modelo pediu {nome}({entrada})")
            if nome == "ajustar_capacidade":
                try:
                    aprovado = input(f"Aprovar ajustar_capacidade {entrada}? [s/N] ").strip().lower() == "s"
                except EOFError:  # sem terminal interativo: nega por padrão
                    aprovado = False
                    print("(sem terminal interativo: ação negada)")
                resultado = executar(nome, entrada) if aprovado else {"erro": "ação negada pelo operador"}
            else:
                resultado = executar(nome, entrada)
                if nome == "ler_metricas":
                    pontos_lidos = max(pontos_lidos, resultado.get("quantidade_de_pontos", 0))
            log({"evento": "ferramenta", "iteracao": iteracao, "ferramenta": nome, "entrada": entrada,
                 "aprovado": aprovado, "resultado": resultado})
            resultados.append({"toolResult": {"toolUseId": uso["toolUseId"], "content": [{"json": resultado}]}})
        msgs.append({"role": "user", "content": resultados})
    print(f"\nLimite de {MAX_ITERACOES} iterações atingido sem conclusão.")
    log({"evento": "limite_iteracoes", "iteracoes": MAX_ITERACOES})


if __name__ == "__main__":
    main()
