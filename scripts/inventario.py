"""Etapa 2: inventário de buckets S3, tabelas DynamoDB e usuários IAM no Floci.
Uso: python3 scripts/inventario.py"""
import boto3

# Endpoint vem do perfil floci (~/.aws/config, endpoint_url). Fixar o perfil aqui evita que o script
# caia no perfil default, que nesta máquina tem credenciais reais.
sessao = boto3.Session(profile_name="floci")
conta = sessao.client("sts").get_caller_identity()["Account"]
assert conta == "000000000000", f"PARE: conta {conta} não é o Floci"

print("Buckets S3:")
for b in sessao.client("s3").list_buckets()["Buckets"]:
    print(f"  - {b['Name']}")
print("Tabelas DynamoDB:")
for t in sessao.client("dynamodb").list_tables()["TableNames"]:
    print(f"  - {t}")
print("Usuários IAM:")
for u in sessao.client("iam").list_users()["Users"]:
    print(f"  - {u['UserName']}")
