output "host" {
  description = "Endereço do serviço PostgreSQL."
  value       = aiven_pg.banco.service_host
}

output "porta" {
  value = aiven_pg.banco.service_port
}

output "banco" {
  value = aiven_pg_database.fomento.database_name
}

output "usuario_carga" {
  value = aiven_pg.banco.service_username
}

output "usuario_leitura" {
  value = aiven_pg_user.leitura.username
}

output "database_url" {
  description = "URL de conexão do usuário de carga. Para ver: terraform output -raw database_url"
  value       = local.url_carga
  sensitive   = true
}

output "database_url_leitura" {
  value     = local.url_leitura
  sensitive = true
}
