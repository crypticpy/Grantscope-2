using '../main.bicep'

param baseName = 'grantscope2'
param location = 'southcentralus'
param imageTag = 'v1.0.0'
param environment = 'prod'
param postgresAdminUser = 'gsadmin'
param enableKeyVault = true
param enablePostgres = true
param enableStorage = true
param postgresAdminPassword = readEnvironmentVariable('PG_ADMIN_PASSWORD', '')
