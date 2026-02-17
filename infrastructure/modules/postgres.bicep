// ---------------------------------------------------------------------------
// PostgreSQL Flexible Server
// Primary database for GrantScope2 with pgvector for semantic search
// ---------------------------------------------------------------------------

@description('Base name for all resources')
param baseName string

@description('Environment suffix (dev, staging, prod)')
param environment string

@description('Azure region for resource deployment')
param location string

@description('Administrator login username')
param adminUser string

@secure()
@description('Administrator login password')
param adminPassword string

// ---------------------------------------------------------------------------
// Resources
// ---------------------------------------------------------------------------

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'psql-${baseName}-${environment}'
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: adminUser
    administratorLoginPassword: adminPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
}

// Require SSL for all connections
resource sslConfig 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: postgresServer
  name: 'require_secure_transport'
  properties: {
    value: 'on'
    source: 'user-override'
  }
}

// Enable pgvector, uuid-ossp, and pgcrypto extensions
resource extensionsConfig 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2024-08-01' = {
  parent: postgresServer
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR,UUID-OSSP,PGCRYPTO'
    source: 'user-override'
  }
  dependsOn: [
    sslConfig
  ]
}

// Create the application database
resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresServer
  name: 'grantscope'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
  dependsOn: [
    extensionsConfig
  ]
}

// Allow Azure services to connect (Container Apps, etc.)
resource firewallAllowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

@description('FQDN of the PostgreSQL server')
output serverFqdn string = postgresServer.properties.fullyQualifiedDomainName

@description('Name of the PostgreSQL server resource')
output serverName string = postgresServer.name
