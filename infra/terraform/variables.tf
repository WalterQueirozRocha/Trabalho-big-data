variable "projeto_aiven" {
  description = "Nome do projeto no Aiven onde o serviço fica. É criado junto com a conta."
  type        = string
}

variable "nome_servico" {
  description = "Nome do serviço PostgreSQL. Não pode ser trocado depois sem recriar o serviço."
  type        = string
  default     = "pg-fomento-cnpq"
}

variable "nuvem" {
  description = "Nuvem e região do serviço. O Aiven só cria serviços gratuitos na DigitalOcean e na UpCloud, nenhuma na América do Sul; do-nyc (Nova York) é a mais próxima."
  type        = string
  default     = "do-nyc"
}

variable "plano" {
  description = "Plano do serviço. free-1-1gb é o Free Tier (1 CPU, 1 GB de RAM e 1 GB de disco)."
  type        = string
  default     = "free-1-1gb"
}

variable "versao_postgres" {
  description = "Versão principal do PostgreSQL."
  type        = string
  default     = "17"
}

variable "nome_banco" {
  description = "Banco criado dentro do serviço para receber a carga."
  type        = string
  default     = "fomento_cnpq"
}

variable "usuario_leitura" {
  description = "Usuário somente leitura usado nas próximas fases (consultas e painéis)."
  type        = string
  default     = "analise_leitura"
}

variable "ips_liberados" {
  description = "Faixas de IP que podem conectar no banco. O padrão libera qualquer IP porque a equipe acessa de redes diferentes; restrinja quando possível."
  type        = list(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = alltrue([for ip in var.ips_liberados : can(cidrnetmask(ip))])
    error_message = "Use faixas no formato CIDR, por exemplo 177.20.0.0/16 ou 200.10.20.30/32."
  }
}

variable "gerar_arquivos_locais" {
  description = "Gera o .env e o ca.pem na raiz do repositório para o ETL usar. Os dois arquivos estão no .gitignore."
  type        = bool
  default     = true
}
