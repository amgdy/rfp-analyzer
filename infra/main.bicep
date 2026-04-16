targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('Location for Azure AI Foundry account and model deployments')
@metadata({azd: {
  type: 'location'
  usageName: [
    'OpenAI.GlobalStandard.gpt-5.2,10'
  ]}
})
param foundryLocation string

@description('The GPT reasoning model name to deploy (e.g. gpt-5.4)')
param reasoningModelName string

@description('The GPT reasoning model version to deploy (e.g. 2026-03-05)')
param reasoningModelVersion string

param rfpAnalyzerExists bool

// Tags that should be applied to all resources.
// 
// Note that 'azd-service-name' tags should be applied separately to service host resources.
// Example usage:
//   tags: union(tags, { 'azd-service-name': <service name in azure.yaml> })
var tags = {
  'azd-env-name': environmentName
  SecurityControl: 'Ignore'
}

var resourceGroupName = 'rg-${environmentName}'

module rfpResourceGroup 'br/public:avm/res/resources/resource-group:0.4.3' = {
  params: { 
    name: resourceGroupName
    location: location
    tags: tags
  }
}



module resources 'resources.bicep' = {
  scope: resourceGroup(resourceGroupName)
  name: 'resources'
  params: {
    location: location
    tags: tags
    rfpAnalyzerExists: rfpAnalyzerExists
    foundryLocation: foundryLocation
    reasoningModelName: reasoningModelName
    reasoningModelVersion: reasoningModelVersion
  }
  dependsOn: [
    rfpResourceGroup
  ]
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_RESOURCE_RFP_ANALYZER_ID string = resources.outputs.AZURE_RESOURCE_RFP_ANALYZER_ID
output AZURE_OPENAI_ENDPOINT string = resources.outputs.AZURE_OPENAI_ENDPOINT
output AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT string = resources.outputs.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
output AZURE_CONTENT_UNDERSTANDING_ENDPOINT string = resources.outputs.AZURE_CONTENT_UNDERSTANDING_ENDPOINT
output SERVICE_RFP_ANALYZER_URL string = resources.outputs.SERVICE_RFP_ANALYZER_URL
