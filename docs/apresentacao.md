# Apresentação (10 min): GenAI na automação AWS, tema agronegócio

Grupo: Felipe Pegoraro, Thiago Siena, Pedro Borges

> Divisão de falas sugerida; ajustar entre nós. Ensaiar com cronômetro: a demo ao vivo depende de um modelo em CPU (cada chamada leva de 10 a 60 s).

## Antes de começar (5 min antes, fora do tempo)

```bash
docker compose up -d && export AWS_PROFILE=floci
aws sts get-caller-identity        # mostrar 000000000000 na abertura
./deploy.sh                        # se o ambiente estiver zerado
```

Deixe abertos: um terminal grande, `docs/arquitetura.md` renderizado (GitHub/VS Code) e `DIARIO_DE_PROMPTS.md`.

## Roteiro

| Tempo | Quem | Tópico | O que mostrar |
|---|---|---|---|
| 0:00–1:00 | Felipe | Problema: técnicos enviam relatórios de lavoura em texto; alguém precisa triar a urgência. Infra de monitoramento sofre picos de CPU. | Slide/título + os três papéis da IA (assistente, componente, agente). |
| 1:00–2:00 | Felipe | Ambiente: Floci + Ollama; por que nunca atinge a conta real. | `aws sts get-caller-identity` → `000000000000`; `docker compose ps`. |
| 2:00–4:00 | Thiago | **IA como componente** (Etapa 4): S3 → Lambda → Bedrock → DynamoDB. | **Ao vivo:** `aws s3 cp etapa4/relatorios/relatorio_alta.txt s3://relatorios-campo/demo.txt`, depois `aws dynamodb scan --table-name triagem`. Diagrama no fundo. |
| 4:00–5:30 | Thiago | **Injeção de prompt**: o sistema obedeceu; delimitar o texto não bastou; a validação da saída barrou. | `evidencias/etapa4/02_scan_sem_defesa.txt` × `05_scan_com_defesa.txt` (urgencia `baixa` → `revisao_humana`). |
| 5:30–7:30 | Pedro | **IA como agente** (Etapa 5): alarme → SNS → SQS; agente com 4 ferramentas, usuário IAM próprio, aprovação humana, log. | **Ao vivo:** `.venv/bin/python etapa5/agente.py`, responder a aprovação; depois `aws logs tail /agente/diagnostico`. Plano B se demorar: mostrar o log de uma execução anterior. |
| 7:30–8:30 | Pedro | **Uso crítico da IA**: erros reais detectados. | Diário: alucinação de API (`boto3.client('asg')`), métricas inventadas, ARN do ASG no Floci, timeout com tool use. Mostrar a guarda "diagnóstico recusado". |
| 8:30–9:30 | Felipe | **Custo e TI Verde**: 500 relatórios/dia ≈ US$ 0,22 (Nova Micro) a US$ 21 (Sonnet) por mês × US$ 384 da GPU; ~2 núcleos e 1,6 GB por inferência. | Tabela de `docs/relatorio_etapa6.md`. |
| 9:30–10:00 | Felipe | Recomendação (híbrido) e o que muda na AWS real. | Seção "Na AWS real" do README. |

## Perguntas prováveis (preparar resposta)

- Por que o modelo errou o relatório médio? (modelo de 1B; na AWS real seria maior; a validação e a revisão humana cobrem.)
- O IAM do Floci é igual ao da AWS? (Não: não avalia o recurso em autoscaling/logs; mostramos o teste e a política com ARN real.)
- A defesa contra injeção é suficiente? (Não sozinha; na AWS real somaríamos Bedrock Guardrails.)
