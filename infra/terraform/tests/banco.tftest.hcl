# Testes com providers simulados: rodam sem conta no Aiven e sem criar nada.
# terraform init && terraform test

mock_provider "aiven" {
  mock_data "aiven_project" {
    defaults = {
      ca_cert = "-----BEGIN CERTIFICATE-----\nteste\n-----END CERTIFICATE-----\n"
    }
  }

  mock_resource "aiven_pg" {
    defaults = {
      service_host     = "pg-fomento-cnpq-teste.aivencloud.com"
      service_port     = 12345
      service_username = "avnadmin"
      service_password = "s3nh@/teste"
    }
  }
}

mock_provider "local" {}

variables {
  projeto_aiven = "projeto-teste"
}

run "servico_no_plano_gratuito" {
  command = plan

  assert {
    condition     = aiven_pg.banco.plan == "free-1-1gb" && aiven_pg.banco.cloud_name == "do-nyc"
    error_message = "O serviço deve usar o Free Tier na região padrão."
  }

  assert {
    condition     = aiven_pg_database.fomento.database_name == "fomento_cnpq"
    error_message = "Nome do banco diferente do esperado."
  }
}

run "env_com_senha_codificada_e_permissao_restrita" {
  command = apply

  assert {
    condition     = strcontains(local_sensitive_file.env[0].content, "DATABASE_URL=postgres://avnadmin:s3nh%40%2Fteste@pg-fomento-cnpq-teste.aivencloud.com:12345/fomento_cnpq?")
    error_message = "A URL de carga no .env está errada ou a senha não foi codificada."
  }

  assert {
    condition     = aiven_pg_user.leitura.password == random_password.leitura.result && length(random_password.leitura.result) == 24
    error_message = "A senha do usuário de leitura deve vir do random_password."
  }

  assert {
    condition     = strcontains(local_sensitive_file.env[0].content, "USUARIO_LEITURA=analise_leitura")
    error_message = "O .env deve informar o usuário de leitura."
  }

  assert {
    condition     = local_sensitive_file.env[0].file_permission == "0600"
    error_message = "O .env deve ficar legível só pelo dono."
  }

  assert {
    condition     = startswith(local_sensitive_file.ca[0].content, "-----BEGIN CERTIFICATE-----")
    error_message = "O ca.pem deve conter o certificado do projeto."
  }
}

run "sem_arquivos_locais_quando_desligado" {
  command = plan

  variables {
    gerar_arquivos_locais = false
  }

  assert {
    condition     = length(local_sensitive_file.env) == 0 && length(local_sensitive_file.ca) == 0
    error_message = "Nenhum arquivo local deveria ser gerado."
  }
}

run "rejeita_faixa_de_ip_invalida" {
  command = plan

  variables {
    ips_liberados = ["minha-casa"]
  }

  expect_failures = [var.ips_liberados]
}
