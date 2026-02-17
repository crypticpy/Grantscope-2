// ---------------------------------------------------------------------------
// Container Apps Environment
// Managed environment for GrantScope2 API and Worker container apps
// ---------------------------------------------------------------------------

@description('Base name for all resources')
param baseName string

@description('Environment suffix (dev, staging, prod)')
param environment string

@description('Azure region for resource deployment')
param location string

@description('Resource ID of the Log Analytics workspace for diagnostics')
param logAnalyticsWorkspaceId string

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${baseName}-${environment}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Resource ID of the Container Apps Environment')
output environmentId string = containerAppsEnvironment.id

@description('Name of the Container Apps Environment')
output environmentName string = containerAppsEnvironment.name
