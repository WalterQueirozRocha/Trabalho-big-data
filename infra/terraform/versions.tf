terraform {
  required_version = ">= 1.7"

  required_providers {
    aiven = {
      source  = "aiven/aiven"
      version = "~> 4.65"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

# O token do Aiven é lido da variável de ambiente AIVEN_TOKEN.
# Ele não aparece em nenhum arquivo do repositório.
provider "aiven" {}
