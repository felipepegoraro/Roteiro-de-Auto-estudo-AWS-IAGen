"""Teste local do laço do agente: aprovação humana, trava de ASG, guarda sem métricas e proposta do código.
Bedrock e AWS simulados (não chama o Floci). Precisa do .credenciais_agente.json do cenario.sh só para importar.
Rodar: .venv/bin/python etapa5/test_agente.py"""
import builtins
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agente as a  # noqa: E402


class Fake:
    def __init__(self, **metodos):
        self.__dict__.update(metodos)


def preparar(respostas_modelo, respostas_operador, cpu):
    estado = {"desejado": 1, "set": [], "logs": []}
    agora = datetime.now(timezone.utc)
    pontos = [{"Timestamp": agora - timedelta(minutes=len(cpu) - i), "Average": v, "Maximum": v} for i, v in enumerate(cpu)]
    a.cw = Fake(get_metric_statistics=lambda **k: {"Datapoints": pontos if k["Dimensions"][0]["Value"] == "asg-campo" else []})
    a.asg = Fake(
        describe_auto_scaling_groups=lambda **k: {"AutoScalingGroups": [{"AutoScalingGroupName": "asg-campo", "MinSize": 1,
                                                                        "MaxSize": 4, "DesiredCapacity": estado["desejado"]}]},
        set_desired_capacity=lambda **k: estado["set"].append(k["DesiredCapacity"]))
    a.logs = Fake(put_log_events=lambda **k: estado["logs"].append(k["logEvents"][0]["message"]), create_log_stream=lambda **k: None)
    a.sessao = Fake(client=lambda *x, **k: Fake(get_caller_identity=lambda: {"Account": "000000000000", "Arn": "teste"}))
    fila = list(respostas_modelo)
    a.bedrock = Fake(converse=lambda **k: fila.pop(0))
    operador = list(respostas_operador)
    builtins.input = lambda _: operador.pop(0)
    sys.argv = ["agente.py"]
    return estado


def ferramenta(nome, entrada, i="t"):
    return {"stopReason": "tool_use", "output": {"message": {"role": "assistant", "content": [
        {"toolUse": {"toolUseId": i, "name": nome, "input": entrada}}]}}}


def texto(t):
    return {"stopReason": "end_turn", "output": {"message": {"role": "assistant", "content": [{"text": t}]}}}


ALTA = [30, 50, 70, 86, 91, 95]
LER = ferramenta("ler_metricas", {"nome_asg": "asg-campo"}, "m")

# 1) modelo pede ajustar_capacidade, operador aprova -> set_desired_capacity(2)
e = preparar([LER, ferramenta("ajustar_capacidade", {"nome_asg": "asg-campo", "capacidade": 2}), texto("feito")], ["s"], ALTA)
a.main()
assert e["set"] == [2], e
# 2) operador nega -> nada escrito
e = preparar([LER, ferramenta("ajustar_capacidade", {"nome_asg": "asg-campo", "capacidade": 2}), texto("ok")], ["n"], ALTA)
a.main()
assert e["set"] == [] and any("negada pelo operador" in m for m in e["logs"]), e
# 3) aprovado, mas fora da trava (outro ASG / capacidade 9) -> nada escrito
e = preparar([LER, ferramenta("ajustar_capacidade", {"nome_asg": "outro", "capacidade": 9}), texto("ok")], ["s"], ALTA)
a.main()
assert e["set"] == [], e
# 4) modelo tenta concluir sem métricas -> recusado; depois lê e conclui
e = preparar([texto("CPU alta, escale"), LER, texto("CPU estável")], [], [40, 41, 42, 43])
a.main()
assert any("diagnostico_recusado" in m for m in e["logs"]) and e["set"] == [], e
# 5) modelo não chama a ferramenta (aqui até recomenda REDUZIR, como nas execuções 5 e 6) + CPU sustentada
#    -> proposta do código (+1) baseada só no cálculo; operador aprova -> set(2)
e = preparar([LER, texto("Ação recomendada: reduzir a capacidade.")], ["s"], ALTA)
a.main()
assert e["set"] == [2] and any("proposta_codigo" in m for m in e["logs"]), e
# 6) modelo recomenda aumentar, mas CPU NÃO sustentada (um pico isolado) -> sem proposta
e = preparar([LER, texto("Ação recomendada: aumentar a capacidade.")], [], [30, 95, 40, 50])
a.main()
assert e["set"] == [] and not any("proposta_codigo" in m for m in e["logs"]), e
print("\nok: 6 casos passaram")
