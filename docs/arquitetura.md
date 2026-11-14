# Arquitetura do protótipo: agronegócio

Grupo: Felipe Pegoraro, Thiago Siena, Pedro Borges

Dois papéis da IA: **componente** (triagem de relatórios, Etapa 4) e **agente** (diagnóstico de Auto Scaling, Etapa 5). Tudo roda no Floci; o Bedrock é atendido pelo Ollama local.

```mermaid
flowchart LR
  subgraph Campo
    T[Técnico de campo]
    OP[Operador]
  end

  subgraph Floci["Floci (AWS emulada, conta 000000000000)"]
    direction LR
    S3[(S3<br/>relatorios-campo)]
    L[Lambda triagem<br/>app.py]
    DDB[(DynamoDB<br/>triagem)]
    BR[Bedrock Runtime<br/>Converse]
    CW[CloudWatch<br/>CPUUtilization]
    AL{{"Alarme<br/>CPU &gt; 80%"}}
    SNS[SNS<br/>alerta-cpu-campo]
    SQS[SQS<br/>alertas-campo]
    ASG["Auto Scaling<br/>asg-campo (1 a 4)"]
    LOGS[(CloudWatch Logs<br/>/agente/diagnostico)]
    IAM[IAM enforcement<br/>role mínima + usuário do agente]
  end

  OLL[Ollama<br/>llama3.2:1b]
  AG["agente.py<br/>até 6 iterações"]

  T -- relatório .txt --> S3
  S3 -- ObjectCreated --> L
  L -- texto delimitado --> BR
  BR -- proxy --> OLL
  L -- valida JSON / injeção --> DDB
  CW --> AL --> SNS --> SQS
  OP -- pergunta --> AG
  AG -- toolConfig --> BR
  AG -- leitura --> CW
  AG -- leitura --> ASG
  AG -->|"set_desired_capacity<br/>após aprovação s/N"| ASG
  AG -- cada chamada --> LOGS
  IAM -.restringe.-> L
  IAM -.restringe.-> AG
```

## Controles de segurança no desenho

| Ponto | Controle |
|---|---|
| Lambda | Role com só `s3:GetObject`, `dynamodb:PutItem`, `bedrock:InvokeModel` (1 modelo) e logs próprios; teste negativo comprovou `AccessDenied`. |
| Prompt | Relatório delimitado em `<relatorio>`, saída validada (`baixa\|media\|alta`), 2 tentativas, depois `revisao_humana`; texto com ordem embutida → `revisao_humana`. |
| Agente | Usuário IAM próprio; trava no código (só `asg-campo`, 1..4); aprovação humana para escrita; máx. 6 iterações; diagnóstico recusado sem métricas; log de cada ferramenta. |

## Na AWS real

O mesmo código roda trocando só o endpoint. O Bedrock passa a usar um modelo real (ex.: Nova Micro), o agente pode ir para o AgentCore Runtime, as métricas vêm do EC2 automaticamente e o CloudTrail registra cada chamada de API.
