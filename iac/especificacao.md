# Especificação (entrada para o assistente de IA)

1. VPC 10.0.0.0/16 com DNS habilitado, em us-east-1, com Internet Gateway.
2. Sub-rede pública 10.0.1.0/24 (us-east-1a, IP público automático) com rota 0.0.0.0/0 para o IGW.
3. Sub-rede privada 10.0.2.0/24 (us-east-1a), sem rota para a internet e sem NAT Gateway.
4. Security Group do web: entrada só TCP 80 de 0.0.0.0/0; nada de SSH.
5. EC2 t3.micro na sub-rede pública, Amazon Linux 2023 via parâmetro SSM, com Apache servindo uma página.
6. Bucket S3 `relatorios-campo-<conta>` (sem acesso público, criptografado) para a Etapa 4.
7. Tabela DynamoDB `triagem-iac`, chave `arquivo` (String), PAY_PER_REQUEST.
8. Todos os recursos com as tags `Projeto=genai-agro` e `CentroDeCusto=ag822`.
9. Outputs: IP público do web, nome do bucket e ARN da tabela.
