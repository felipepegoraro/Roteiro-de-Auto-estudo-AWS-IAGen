# Mapa de serviços: papel da IA, modelo de serviço e emulação no Floci

> **RASCUNHO**: revisar e reescrever com as nossas palavras antes da entrega. As classificações IaaS/PaaS/SaaS são argumentação nossa (competência 93).

Grupo: Felipe Pegoraro, Thiago Siena, Pedro Borges

| Serviço | Papel da IA | IaaS/PaaS/SaaS | Justificativa | Emulação no Floci (observado neste projeto) |
|---|---|---|---|---|
| **Amazon Bedrock** | Componente | PaaS | Plataforma gerenciada: entrega modelos por API, e nós escrevemos a aplicação que os chama; não gerenciamos servidor nem modelo. | **Parcial.** Converse e tool use repassados ao Ollama (funcionou); modelos pequenos; InvokeModel só com resposta fixa; listagem de modelos não emulada. |
| **Amazon Bedrock AgentCore** | Agente | PaaS | Ambiente gerenciado para executar, identificar e observar agentes; o código do agente é nosso. | **Parcial (só plano de controle).** Registra recursos, mas não executa o agente. Não testado por nós. |
| **Kiro (IDE/CLI)** | Assistente | SaaS | Produto pronto usado pelo desenvolvedor, com login e plano de assinatura. | **Não se aplica** (é cliente, não API da AWS). Pode apontar para o Floci pelo perfil. |
| **Agent Toolkit for AWS** | Ponte | SaaS / serviço gerenciado | AWS MCP Server gerenciado + skills; só opera contas reais e registra no CloudTrail. | **Não emulado.** |
| **awslabs/mcp** | Ponte (aberta) | Software open source | Servidores MCP que rodam localmente (stdio) ou remotos. | Os de documentação não precisam de conta; os que acessam recursos funcionam com `AWS_PROFILE=floci` no `env`. |
| **Lambda** | Executa o componente | PaaS (serverless) | Só enviamos o código; a AWS gerencia a execução. | **Completo para o nosso uso**: containers Docker reais, role com credenciais temporárias avaliadas pelo IAM. |
| **S3 / DynamoDB / SNS / SQS** | Infra do fluxo | PaaS | Serviços gerenciados de dados/mensagens. | **Completo para o nosso uso**: notificação S3 → Lambda e alarme → SNS → SQS funcionaram. |
| **EC2 / Auto Scaling / CloudWatch** | Alvo do agente | IaaS (EC2) / PaaS | EC2 entrega máquina virtual; o resto é gerenciado. | **Parcial**: instâncias emuladas, sem IP público real, métricas só via `put-metric-data`, alarmes funcionam. IAM não avalia o recurso em autoscaling/logs. |
| **CloudFormation** | IaC | PaaS | Orquestração gerenciada de recursos. | **Parcial**: deploy/delete funcionaram; não resolve `AWS::SSM::Parameter::Value` no `ImageId`. |

## Por que o emulador imita a API do Bedrock, mas não a qualidade

A API é um contrato (formato JSON da requisição e da resposta). O Floci implementa esse contrato e traduz para o Ollama, então o nosso `boto3` não percebe a diferença. A qualidade depende do modelo por trás: um modelo de 1B parâmetros em CPU não tem a capacidade de um modelo grande no Bedrock. Nós vimos isso na prática: o agente inventou métricas e uma API inexistente. O que observamos aqui vale como piso, não como teto.

## MCP local (stdio) × remoto (5 linhas)

1. Local (stdio): o cliente de IA inicia o servidor como processo na própria máquina (ex.: `uvx awslabs.aws-documentation-mcp-server`).
2. A comunicação é pela entrada/saída padrão, sem rede; herda as variáveis de ambiente do bloco `env` (ex.: `AWS_PROFILE=floci`).
3. Remoto: o servidor roda em outro lugar e é acessado por HTTP (ex.: `https://knowledge-mcp.global.api.aws`).
4. O remoto não precisa de instalação, mas depende de rede e da confiança no provedor; credenciais e dados saem da máquina.
5. Para recursos do Floci, o local é o adequado; para documentação pública, os dois servem.

## Pergunta de checagem (Etapa 1)

Se o modelo cita um serviço AWS que não existe, **RAG** (ou um servidor MCP de documentação) reduz o problema: a resposta passa a se apoiar em documentação oficial recuperada na hora, e não só na memória do modelo, que pode "completar" nomes plausíveis.
