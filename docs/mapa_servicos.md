# Mapa de serviços: papel da IA, modelo de serviço e emulação no Floci

Grupo: Felipe Pegoraro, Thiago Siena, Pedro Borges

A classificação em IaaS/PaaS/SaaS é a nossa argumentação (competência 93). A última coluna é o que vimos funcionando ou falhando no Floci durante o projeto.

| Serviço | Papel da IA | IaaS/PaaS/SaaS | Por que classificamos assim | No Floci (o que observamos) |
|---|---|---|---|---|
| **Amazon Bedrock** | Componente | PaaS | A AWS entrega o modelo pronto por API. A aplicação que chama é nossa, mas não cuidamos de servidor nem do modelo. | **Parcial.** Converse e tool use funcionaram, repassados ao Ollama. Os modelos são pequenos, o InvokeModel devolve uma resposta fixa e a listagem de modelos não existe. |
| **Amazon Bedrock AgentCore** | Agente | PaaS | É um ambiente gerenciado para rodar, identificar e monitorar agentes. O código do agente continua sendo nosso. | **Parcial, só o plano de controle.** Registra os recursos, mas não executa o agente. Não chegamos a testar. |
| **Kiro (IDE/CLI)** | Assistente | SaaS | É um produto pronto para o desenvolvedor, com login e assinatura. Não montamos nada, só usamos. | **Não se aplica**, porque é um cliente e não uma API da AWS. Dá para apontar para o Floci pelo perfil. |
| **Agent Toolkit for AWS** | Ponte | SaaS / serviço gerenciado | É o AWS MCP Server gerenciado pela AWS, com skills prontas. Só funciona com conta real e registra tudo no CloudTrail. | **Não emulado.** |
| **awslabs/mcp** | Ponte (aberta) | Software open source | São servidores MCP que a gente baixa e roda na própria máquina (stdio) ou acessa remotamente. | Os de documentação não precisam de conta. Os que mexem em recursos funcionam com `AWS_PROFILE=floci` no `env`. |
| **Lambda** | Roda o componente | PaaS (serverless) | Mandamos só o código e a AWS cuida de onde e quando ele roda. | **Completo para o nosso uso.** Sobe containers Docker de verdade e a role recebe credenciais temporárias avaliadas pelo IAM. |
| **S3 / DynamoDB / SNS / SQS** | Infra do fluxo | PaaS | São serviços gerenciados de armazenamento e mensagens. Não existe máquina para administrar. | **Completo para o nosso uso.** A notificação S3 → Lambda e o caminho alarme → SNS → SQS funcionaram. |
| **EC2 / Auto Scaling / CloudWatch** | Alvo do agente | IaaS (EC2) / PaaS | A EC2 é uma máquina virtual e o sistema dentro dela é responsabilidade nossa. Auto Scaling e CloudWatch são gerenciados. | **Parcial.** As instâncias são emuladas e sem IP público real, a métrica de CPU só existe se a gente publicar com `put-metric-data` e os alarmes funcionam. O IAM não avalia o recurso em autoscaling e logs. |
| **CloudFormation** | IaC | PaaS | A AWS cria e apaga os recursos a partir do template. A gente só descreve o que quer. | **Parcial.** Deploy e delete funcionaram, mas ele não resolve `AWS::SSM::Parameter::Value` no `ImageId`. |

## Por que o emulador imita a API do Bedrock, mas não a qualidade

A API é só um contrato: o formato do JSON que vai e do que volta. O Floci segue esse contrato e repassa a chamada para o Ollama, então o nosso `boto3` não percebe diferença nenhuma. Já a qualidade da resposta depende do modelo que está por trás, e um modelo de 1B em CPU não chega perto de um modelo grande do Bedrock. Vimos isso no projeto: o agente inventou métricas e uma API que não existe. Por isso tratamos o que medimos aqui como o pior caso, não como o resultado esperado na AWS real.

## MCP local (stdio) × remoto

1. No local (stdio), o próprio cliente de IA abre o servidor como um processo na máquina, por exemplo `uvx awslabs.aws-documentation-mcp-server`.
2. A conversa é pela entrada e saída padrão, sem rede, e o servidor herda as variáveis do bloco `env`, como `AWS_PROFILE=floci`.
3. No remoto, o servidor fica em outro lugar e é acessado por HTTP, por exemplo `https://knowledge-mcp.global.api.aws`.
4. O remoto não precisa instalar nada, mas depende da rede e de confiar em quem o hospeda, porque credenciais e dados saem da máquina.
5. Para mexer nos recursos do Floci o local é o certo. Para documentação pública, qualquer um dos dois serve.

## Pergunta de checagem (Etapa 1)

Se o modelo cita um serviço da AWS que não existe, o que ajuda é o **RAG** (ou um servidor MCP de documentação). A resposta passa a se apoiar na documentação oficial buscada na hora, e não só na memória do modelo, que tende a completar com nomes que parecem plausíveis.
