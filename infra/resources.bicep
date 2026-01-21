@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}


param rfpAnalyzerExists bool

@description('The location for Microsoft Foundry project deployments')
param foundryLocation string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = substring(toLower(uniqueString(subscription().id, resourceGroup().id, location)), 0, 6)


var modelName = 'gpt-5.2'
var modelVersion = '2025-12-11'

var defaultOpenAiDeployments = [
  {
    name: modelName
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    sku: {
      name: 'GlobalStandard'
      capacity: 100
    }
  }
  {
    name: 'gpt-4.1'
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1'
      version: '2025-04-14'
    }
    sku: {
      name: 'GlobalStandard'
      capacity: 100
    }
  }
  {
    name: 'gpt-4.1-mini'
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1-mini'
      version: '2025-04-14'
    }
    sku: {
      name: 'GlobalStandard'
      capacity: 100
    }
  }
  {
    name: 'text-embedding-3-large'
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    sku: {
      name: 'GlobalStandard'
      capacity: 300
    }
  }
]


// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.2.1' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}


var foundryProjectName = 'proj-rfpa-${resourceToken}'
var foundryAccountName = '${abbrs.aiFoundryAccounts}-rfpa-${resourceToken}'

// Microsoft Foundry Resource
module foundryAccount 'br/public:avm/res/cognitive-services/account:0.14.1' = {
  name: 'foundry-project'
  params:{
    name: foundryAccountName
    kind: 'AIServices'
    location: location
    tags: tags
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    customSubDomainName: foundryAccountName
    allowProjectManagement: true
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [rfpAnalyzerIdentity.outputs.resourceId]
    }
    deployments: defaultOpenAiDeployments
    disableLocalAuth: true
  }
}

// Get existing Foundry Account Resource
resource foundryAccountResource 'Microsoft.CognitiveServices/accounts@2025-09-01' existing = {
  name: foundryAccountName
  dependsOn: [
    foundryAccount
  ]
}

// Microsoft Foundry Project Resource
resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-09-01' = {
  name: foundryProjectName
  parent: foundryAccountResource
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: foundryProjectName
    description: 'RFP Analyzer Foundry Project'
  }
}

// Application Insights Connection to Foundry Project
resource appInsightsFoundryConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-09-01' = {
  name: '${foundryAccountName}-appinsights'
  parent: foundryProject
  properties: {
    category: 'AppInsights'
    target: monitoring.outputs.applicationInsightsResourceId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: monitoring.outputs.applicationInsightsConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: monitoring.outputs.applicationInsightsResourceId
    }
  }
}

var azureOpenAiEndpoint = foundryAccount.outputs.endpoints['OpenAI Language Model Instance API']
var documentIntelligenceEndpoint = foundryAccount.outputs.endpoints['FormRecognizer']
var contentUnderstandingEndpoint = foundryAccount.outputs.endpoints['Content Understanding']



module rfpAnalyzerIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: 'rfpAnalyzeridentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}rfpAnalyzer-${resourceToken}'
    location: location
  }
}

// Container registry
module containerRegistry 'br/public:avm/res/container-registry/registry:0.10.0' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    acrSku: 'Standard'
    zoneRedundancy:'Disabled'
    acrAdminUserEnabled: false
    exportPolicyStatus: 'enabled'
    enableTelemetry: true
    roleAssignments:[
      {
        principalId: rfpAnalyzerIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
    ]
  }
}

// Container apps environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.10.2' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
    publicNetworkAccess: 'Enabled'
    tags: tags
    enableTelemetry: true
  }
}

module rfpAnalyzerFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'rfpAnalyzer-fetch-image'
  params: {
    exists: rfpAnalyzerExists
    name: 'rfp-analyzer'
  }
}

module rfpAnalyzer 'br/public:avm/res/app/container-app:0.20.0' = {
  name: 'rfpAnalyzer'
  params: {
    name: 'rfp-analyzer'
    ingressTargetPort: 8501
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 10
    }    
    containers: [
      {
        image: rfpAnalyzerFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('2')
          memory: '4.0Gi'
        }
        env: [
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: rfpAnalyzerIdentity.outputs.clientId
          }
          {
            name: 'AZURE_CONTENT_UNDERSTANDING_ENDPOINT'
            value: contentUnderstandingEndpoint
          }
          {
            name: 'AZURE_OPENAI_ENDPOINT'
            value: '${azureOpenAiEndpoint}/openai/'
          }
          {
            name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
            value: modelName
          }
          {
            name: 'AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME'
            value: modelName
          }
          {
            name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
            value: documentIntelligenceEndpoint
          }
          {
            name: 'PORT'
            value: '8501'
          }
        ]
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [rfpAnalyzerIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: rfpAnalyzerIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'rfp-analyzer' })
    enableTelemetry: true
  }
}

module rfpAnalyzerbackendRoleAzureAIDeveloperRG 'br/public:avm/res/authorization/role-assignment/rg-scope:0.1.1' = {
  params: {
    // Required parameters
    principalId: rfpAnalyzerIdentity.outputs.principalId
    roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '64702f94-c441-49e6-a78b-ef80e0188fee') 
    // Non-required parameters
    principalType: 'ServicePrincipal'
    description: 'Role assignment for Azure AI Developer in Resource Group scope'
  }
}

module rfpAnalyzerbackendRoleCognitiveServicesUserRG 'br/public:avm/res/authorization/role-assignment/rg-scope:0.1.1' = {
  params: {
    // Required parameters
    principalId: rfpAnalyzerIdentity.outputs.principalId
    roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') 
    // Non-required parameters
    principalType: 'ServicePrincipal'
    description: 'Role assignment for Cognitive Services User in Resource Group scope'
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_RFP_ANALYZER_ID string = rfpAnalyzer.outputs.resourceId
output AZURE_OPENAI_ENDPOINT string = azureOpenAiEndpoint
output AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT string = documentIntelligenceEndpoint
output AZURE_CONTENT_UNDERSTANDING_ENDPOINT string = contentUnderstandingEndpoint
