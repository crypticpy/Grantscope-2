// ---------------------------------------------------------------------------
// Container App — Worker
// Background job processor for GrantScope2 discovery, research, and briefs
// ---------------------------------------------------------------------------

@description('Base name for all resources')
param baseName string

@description('Environment suffix (dev, staging, prod)')
param environment string

@description('Azure region for resource deployment')
param location string

@description('Resource ID of the Container Apps Environment')
param containerAppsEnvironmentId string

@description('ACR login server FQDN (e.g. acrgrantscope2prod.azurecr.io)')
param acrLoginServer string

@description('Docker image tag to deploy')
param imageTag string

@description('Name of the Key Vault containing application secrets')
param keyVaultName string

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

resource workerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${baseName}-worker-${environment}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'database-url'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/database-url'
          identity: 'system'
        }
        {
          name: 'azure-storage-connection-string'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/azure-storage-connection-string'
          identity: 'system'
        }
        {
          name: 'azure-openai-api-key'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/azure-openai-api-key'
          identity: 'system'
        }
        {
          name: 'azure-openai-endpoint'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/azure-openai-endpoint'
          identity: 'system'
        }
        {
          name: 'supabase-url'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/supabase-url'
          identity: 'system'
        }
        {
          name: 'supabase-service-key'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/supabase-service-key'
          identity: 'system'
        }
        {
          name: 'tavily-api-key'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/tavily-api-key'
          identity: 'system'
        }
        {
          name: 'firecrawl-api-key'
          keyVaultUrl: 'https://${keyVaultName}.vault.azure.net/secrets/firecrawl-api-key'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: '${acrLoginServer}/grantscope2-api:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'azure-storage-connection-string' }
            { name: 'AZURE_OPENAI_KEY', secretRef: 'azure-openai-api-key' }
            { name: 'AZURE_OPENAI_ENDPOINT', secretRef: 'azure-openai-endpoint' }
            { name: 'SUPABASE_URL', secretRef: 'supabase-url' }
            { name: 'SUPABASE_SERVICE_KEY', secretRef: 'supabase-service-key' }
            { name: 'TAVILY_API_KEY', secretRef: 'tavily-api-key' }
            { name: 'FIRECRAWL_API_KEY', secretRef: 'firecrawl-api-key' }
            { name: 'GRANTSCOPE_PROCESS_TYPE', value: 'worker' }
            { name: 'ENVIRONMENT', value: 'production' }
            { name: 'PORT', value: '8000' }
            { name: 'GRANTSCOPE_ENABLE_SCHEDULER', value: 'true' }
            { name: 'GRANTSCOPE_WORKER_HEALTH_SERVER', value: 'true' }
            { name: 'AZURE_OPENAI_API_VERSION', value: '2024-12-01-preview' }
            { name: 'AZURE_OPENAI_DEPLOYMENT_CHAT', value: 'gpt-4.1' }
            { name: 'AZURE_OPENAI_DEPLOYMENT_CHAT_MINI', value: 'gpt-4.1-mini' }
            { name: 'AZURE_OPENAI_DEPLOYMENT_EMBEDDING', value: 'text-embedding-ada-002' }
            { name: 'SEARCH_PROVIDER', value: 'tavily' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health'
                port: 8000
              }
              periodSeconds: 30
              timeoutSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Name of the Worker container app')
output appName string = workerApp.name

@description('System-assigned managed identity principal ID')
output principalId string = workerApp.identity.principalId
