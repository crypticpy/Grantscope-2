// ---------------------------------------------------------------------------
// Azure Key Vault
// Secrets management for GrantScope2 API keys, connection strings, passwords
// ---------------------------------------------------------------------------

@description('Base name for all resources')
param baseName string

@description('Azure region for resource deployment')
param location string

@description('Environment suffix (dev, staging, prod)')
param environment string

@description('Azure AD tenant ID for RBAC authorization')
param tenantId string = subscription().tenantId

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

// Truncate environment to 3 chars for Key Vault naming (24-char limit)
var envShort = take(environment, 3)

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-${baseName}-${envShort}'
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Name of the Key Vault resource')
output vaultName string = keyVault.name

@description('URI of the Key Vault')
output vaultUri string = keyVault.properties.vaultUri
