"""Etapa 6: projeta o custo mensal da triagem a partir dos tokens gravados no DynamoDB (Etapa 4).
Uso: AWS_PROFILE=floci python3 scripts/custo.py [relatorios_por_dia]"""
import os
import sys

import boto3

# US$ por 1M de tokens (entrada, saída), us-east-1, on-demand.
# CONFERIR na página oficial antes de usar: https://aws.amazon.com/bedrock/pricing/
PRECOS = {
    "Amazon Nova Micro": (0.035, 0.14),
    "Amazon Nova Lite": (0.06, 0.24),
    "Claude Haiku 4.5": (1.00, 5.00),
    "Claude Sonnet 4.5": (3.00, 15.00),
}
EC2_GPU_HORA = 0.526  # g4dn.xlarge on-demand us-east-1 (conferir)
HORAS_MES, DIAS_MES = 730, 30


def medias_tokens():
    sessao = boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "floci"))
    conta = sessao.client("sts").get_caller_identity()["Account"]
    assert conta == "000000000000", f"PARE: conta {conta} não é o Floci"
    itens = sessao.resource("dynamodb").Table("triagem").scan()["Items"]  # obs: 1 página basta p/ poucos itens
    assert itens, "tabela triagem vazia: rode a Etapa 4 antes"
    t_in = sum(int(i["tokens_in"]) for i in itens) / len(itens)
    t_out = sum(int(i["tokens_out"]) for i in itens) / len(itens)
    return len(itens), t_in, t_out


def projetar(t_in, t_out, por_dia):
    linhas = []
    for modelo, (p_in, p_out) in PRECOS.items():
        por_rel = (t_in * p_in + t_out * p_out) / 1e6
        mensal = por_rel * por_dia * DIAS_MES
        equilibrio = EC2_GPU_HORA * HORAS_MES / (por_rel * DIAS_MES)  # relatórios/dia em que a GPU empata
        linhas.append((modelo, por_rel, mensal, equilibrio))
    return linhas


def main():
    por_dia = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    n, t_in, t_out = medias_tokens()
    ec2 = EC2_GPU_HORA * HORAS_MES
    print(f"Itens medidos: {n} | média por relatório: {t_in:.1f} tokens de entrada, {t_out:.1f} de saída")
    print(f"Volume: {por_dia} relatórios/dia = {por_dia * DIAS_MES} por mês\n")
    print(f"| Modelo | US$/relatório | US$/mês | Equilíbrio com EC2 GPU (relatórios/dia) |")
    print(f"|---|---:|---:|---:|")
    for modelo, por_rel, mensal, eq in projetar(t_in, t_out, por_dia):
        print(f"| {modelo} | {por_rel:.7f} | {mensal:.2f} | {eq:,.0f} |")
    print(f"| EC2 g4dn.xlarge 24 h (modelo local) | - | {ec2:.2f} | - |")
    print("| Regras fixas por palavra-chave (sem IA) | ~0 | ~0 (só Lambda/DynamoDB, comuns a todas) | - |")


if __name__ == "__main__":
    # auto-checagem da conta: 100 in/100 out no Nova Micro = 100*0.035/1e6 + 100*0.14/1e6
    assert abs(projetar(100, 100, 1)[0][1] - 1.75e-5) < 1e-12
    main()
