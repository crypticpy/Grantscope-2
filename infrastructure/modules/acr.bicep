// ---------------------------------------------------------------------------
// Azure Container Registry
// Docker image store for GrantScope2 container images
// ---------------------------------------------------------------------------

@description('Base name for all resources')
param baseName string

@description('Azure region for resource deployment')
param location string

@description('Environment suffix (dev, staging, prod)')
param environment string

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: 'acr${baseName}${environment}'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    adminUserEnabled: true
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('ACR login server FQDN')
output acrLoginServer string = acr.properties.loginServer

@description('ACR resource name')
output acrName string = acr.name
