// ---------------------------------------------------------------------------
// Azure Static Web App
// React SPA hosting for the GrantScope2 frontend
// ---------------------------------------------------------------------------

@description('Base name for all resources')
param baseName string

@description('Environment suffix (dev, staging, prod)')
param environment string

@description('Azure region for resource deployment (use centralus for SWA Free tier)')
param location string = 'centralus'

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: 'swa-${baseName}-${environment}'
  location: location
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    stagingEnvironmentPolicy: 'Enabled'
    allowConfigFileUpdates: true
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('Name of the Static Web App resource')
output swaName string = staticWebApp.name

@description('Default hostname of the Static Web App')
output swaDefaultHostname string = staticWebApp.properties.defaultHostname
