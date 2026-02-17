// ===========================================================================
// GrantScope2 — Main Infrastructure Orchestration
// City of Austin AI-powered grant discovery platform
// Resource Group: rg-aph-cognitive-sandbox-dev-scus-01 (South Central US)
// ===========================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Base name for all resources')
param baseName string = 'grantscope2'

@description('Azure region')
param location string = resourceGroup().location

@description('Container image tag')
param imageTag string

@description('Environment suffix')
@allowed([
  'dev'
  'staging'
  'prod'
])
param environment string = 'prod'

@description('Enable Key Vault deployment')
param enableKeyVault bool = true

@description('Enable PostgreSQL deployment')
param enablePostgres bool = true

@description('Enable Storage Account deployment')
param enableStorage bool = true

@secure()
@description('PostgreSQL admin password')
param postgresAdminPassword string

@description('PostgreSQL admin username')
param postgresAdminUser string = 'gsadmin'

// ---------------------------------------------------------------------------
// 1. Log Analytics Workspace
// ---------------------------------------------------------------------------

module logAnalytics './modules/log-analytics.bicep' = {
  name: 'deploy-log-analytics'
  params: {
    baseName: baseName
    location: location
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// 2. Azure Container Registry
// ---------------------------------------------------------------------------

module acr './modules/acr.bicep' = {
  name: 'deploy-acr'
  params: {
    baseName: baseName
    location: location
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// 3. Key Vault (conditional)
// ---------------------------------------------------------------------------

module keyVault './modules/key-vault.bicep' = if (enableKeyVault) {
  name: 'deploy-key-vault'
  params: {
    baseName: baseName
    location: location
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// 4. Storage Account (conditional)
// ---------------------------------------------------------------------------

module storage './modules/storage.bicep' = if (enableStorage) {
  name: 'deploy-storage'
  params: {
    baseName: baseName
    location: location
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// 5. PostgreSQL Flexible Server (conditional)
//    Module created by another agent
// ---------------------------------------------------------------------------

module postgres './modules/postgres.bicep' = if (enablePostgres) {
  name: 'deploy-postgres'
  params: {
    baseName: baseName
    location: location
    environment: environment
    adminUser: postgresAdminUser
    adminPassword: postgresAdminPassword
  }
}

// ---------------------------------------------------------------------------
// 6. Container Apps Environment
//    Module created by another agent
// ---------------------------------------------------------------------------

module containerAppsEnv './modules/container-apps-env.bicep' = {
  name: 'deploy-container-apps-env'
  params: {
    baseName: baseName
    location: location
    environment: environment
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
  }
}

// ---------------------------------------------------------------------------
// 7. API Container App
//    Module created by another agent
// ---------------------------------------------------------------------------

module apiApp './modules/container-app-api.bicep' = {
  name: 'deploy-container-app-api'
  params: {
    baseName: baseName
    location: location
    environment: environment
    imageTag: imageTag
    containerAppsEnvironmentId: containerAppsEnv.outputs.environmentId
    acrLoginServer: acr.outputs.acrLoginServer
    keyVaultName: enableKeyVault ? keyVault.outputs.vaultName : ''
  }
}

// ---------------------------------------------------------------------------
// 8. Worker Container App
//    Module created by another agent
// ---------------------------------------------------------------------------

module workerApp './modules/container-app-worker.bicep' = {
  name: 'deploy-container-app-worker'
  params: {
    baseName: baseName
    location: location
    environment: environment
    imageTag: imageTag
    containerAppsEnvironmentId: containerAppsEnv.outputs.environmentId
    acrLoginServer: acr.outputs.acrLoginServer
    keyVaultName: enableKeyVault ? keyVault.outputs.vaultName : ''
  }
}

// ---------------------------------------------------------------------------
// 9. Static Web App (React SPA)
//    Module created by another agent
// ---------------------------------------------------------------------------

module staticWebApp './modules/static-web-app.bicep' = {
  name: 'deploy-static-web-app'
  params: {
    baseName: baseName
    location: location
    environment: environment
  }
}

// ---------------------------------------------------------------------------
// 10. RBAC Role Assignments
//     Managed identity → ACR and Key Vault access is assigned post-deployment
//     via deploy.sh (az role assignment create) because principalId is only
//     known after the container apps are created.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('API Container App system-assigned identity principal ID')
output apiPrincipalId string = apiApp.outputs.principalId

@description('Worker Container App system-assigned identity principal ID')
output workerPrincipalId string = workerApp.outputs.principalId

@description('ACR resource name')
output acrName string = acr.outputs.acrName

@description('FQDN of the API Container App')
output apiAppFqdn string = apiApp.outputs.fqdn

@description('Name of the Worker Container App')
output workerAppName string = workerApp.outputs.appName

@description('ACR login server FQDN')
output acrLoginServer string = acr.outputs.acrLoginServer

@description('PostgreSQL server FQDN')
output postgresServerFqdn string = enablePostgres ? postgres.outputs.serverFqdn : ''

@description('Storage Account name')
output storageAccountName string = enableStorage ? storage.outputs.storageAccountName : ''

@description('Key Vault name')
output keyVaultName string = enableKeyVault ? keyVault.outputs.vaultName : ''
