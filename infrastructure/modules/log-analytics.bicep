// ---------------------------------------------------------------------------
// Log Analytics Workspace
// Centralized logging for GrantScope2 Container Apps and diagnostics
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

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${baseName}-${environment}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the Log Analytics workspace')
output workspaceId string = logAnalytics.id
