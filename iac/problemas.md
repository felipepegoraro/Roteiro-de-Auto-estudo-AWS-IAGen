# Etapa 3: auditoria do template gerado por IA

Grupo: Felipe Pegoraro, Thiago Siena, Pedro Borges

- Especificação (entrada): `especificacao.md`
- Primeira versão gerada: `vpc_v1_gerado.yaml` · versão final revisada: `vpc.yaml`
- Evidências: `evidencias/etapa3/` (cfn-lint, deploy, verificação)

## Checklist do roteiro aplicado à v1

| Item | Resultado na v1 |
|---|---|
| SG libera 0.0.0.0/0 em porta ≠ 80/443 (ex.: SSH)? | Não. Só TCP 80. |
| AMI fixa ou via parâmetro SSM? | Via SSM (`al2023-ami-kernel-default-x86_64`). No Floci o parâmetro não foi resolvido (ver P4). |
| Outputs úteis (IP, bucket, ARN da tabela)? | Sim, mas sem descrição nem `Export`; no Floci o "IP público" é o privado (P5). |
| Tags de custo por projeto? | Sim: `Projeto=genai-agro`, `CentroDeCusto=ag822` em todo recurso que aceita tag. |
| Serviço/propriedade que não existe (alucinação)? | Não encontrada (cfn-lint sem erro `E`). |
| Algum recurso falhou no Floci? | Nenhum falhou; duas diferenças silenciosas do emulador (P4, P5). |
| Criou NAT Gateway desnecessário? | Não (`describe-nat-gateways` = 0). A especificação pedia isso explicitamente. |

## Problemas encontrados e correções

| # | Problema | Como foi encontrado | Origem | Correção em `vpc.yaml` |
|---|---|---|---|---|
| P1 | Availability Zone fixa `us-east-1a` nas duas sub-redes | `cfn-lint` W3010 | template | `!Select [0, !GetAZs ""]` |
| P2 | Sub-rede privada sem tabela de rotas própria: usava a *main* implicitamente. Se alguém pusesse rota 0.0.0.0/0 na main, a "privada" viraria pública sem ninguém perceber | `describe-route-tables` após o deploy (main sem sub-redes associadas) | template | `RotaPrivada` + `AssocPrivada` explícitas, só com a rota `local` |
| P3 | Instância `Web` sem dependência da rota para a internet: na AWS real pode bootar antes da rota existir e o `dnf install httpd` do UserData falha | revisão manual | template | `DependsOn: RotaInternet` |
| P4 | `ImageId` da instância ficou com o **caminho** do parâmetro SSM, não com a AMI (o parâmetro existe e vale `ami-0abcdef1234567891`) | `describe-instances` | **limitação do Floci** (o CloudFormation dele não resolve `AWS::SSM::Parameter::Value<...>`) | nenhuma no template: na AWS real o tipo de parâmetro resolve. Mantido o SSM, que é o certo |
| P5 | `GetAtt Web.PublicIp` devolve `10.0.1.10` (IP privado) | Outputs do stack | **limitação do Floci** (instâncias emuladas, sem IP público real) | `Description` do Output documenta isso |
| P6 | Outputs sem `Description` nem `Export`, então outros stacks não conseguem referenciar o bucket e a tabela | revisão manual | template | `Description` em todos + `Export` do bucket e do ARN da tabela |

## Pergunta de checagem

Um template que implanta sem erro no Floci **não** está pronto para a AWS real. Exemplos do nosso caso: (1) o Floci aceitou o `ImageId` com um caminho inválido, e só a AWS verificaria se a AMI existe na região; (2) cotas e limites (VPCs e IPs elásticos por região) e permissões IAM de quem implanta só são checados na conta real; (3) custo: a EC2 cobra por hora até o `delete-stack`, enquanto no Floci nada é cobrado.

## Na AWS real

`aws cloudformation validate-template` + change set revisado antes do `deploy`; apagar o stack ao fim do laboratório.
