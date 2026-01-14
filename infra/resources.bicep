@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}


param rfpAnalyzerExists bool

@description('Id of the user or app to assign application roles')
param principalId string

@description('Principal type of user or app')
param principalType string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)

// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
  }
}
// Container registry
module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    publicNetworkAccess: 'Enabled'
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
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.4.5' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
  }
}

module rfpAnalyzerIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'rfpAnalyzeridentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}rfpAnalyzer-${resourceToken}'
    location: location
  }
}
module rfpAnalyzerFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'rfpAnalyzer-fetch-image'
  params: {
    exists: rfpAnalyzerExists
    name: 'rfp-analyzer'
  }
}

module rfpAnalyzer 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'rfpAnalyzer'
  params: {
    name: 'rfp-analyzer'
    ingressTargetPort: 8501
    scaleMinReplicas: 1
    scaleMaxReplicas: 10
    secrets: {
      secureList:  [
      ]
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
            name: 'PORT'
            value: '8501'
          }
          {
            name: 'AZURE_AI_ENDPOINT'
            value: 'https://shld-aoai-aihub-swc-01.services.ai.azure.com/'
          }
          {
            name: 'AZURE_OPENAI_ENDPOINT'
            value: 'https://shld-aoai-aihub-swc-01.openai.azure.com/openai/'
          }
          {
            name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
            value: 'gpt-5.2'
          }
          {
            name: 'AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME'
            value: 'gpt-5.2'
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
  }
}
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_RFP_ANALYZER_ID string = rfpAnalyzer.outputs.resourceId
