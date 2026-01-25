# Post-provision hook to set Content Understanding defaults
# This script is executed by Azure Developer CLI after provisioning

$ErrorActionPreference = "Stop"

Write-Host "Setting Content Understanding defaults..."

# Get the Content Understanding endpoint from azd env
$ContentUnderstandingEndpoint = azd env get-value AZURE_CONTENT_UNDERSTANDING_ENDPOINT 2>$null

if ([string]::IsNullOrEmpty($ContentUnderstandingEndpoint)) {
    Write-Error "Error: AZURE_CONTENT_UNDERSTANDING_ENDPOINT not found in azd environment"
    exit 1
}

Write-Host "Content Understanding Endpoint: $ContentUnderstandingEndpoint"

# Get access token for Azure Cognitive Services
Write-Host "Obtaining access token..."
$AccessToken = az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv

if ([string]::IsNullOrEmpty($AccessToken)) {
    Write-Error "Error: Failed to obtain access token"
    exit 1
}

# Set the default model deployments for Content Understanding
$ApiUrl = "${ContentUnderstandingEndpoint}contentunderstanding/defaults?api-version=2025-11-01"

Write-Host "Calling Content Understanding API to set defaults..."
Write-Host "URL: $ApiUrl"

$Body = @{
    modelDeployments = @{
        "gpt-4.1" = "gpt-4.1"
        "gpt-4.1-mini" = "gpt-4.1-mini"
        "text-embedding-3-large" = "text-embedding-3-large"
    }
} | ConvertTo-Json -Depth 10

$Headers = @{
    "Authorization" = "Bearer $AccessToken"
    "Content-Type" = "application/json"
}

try {
    $Response = Invoke-RestMethod -Uri $ApiUrl -Method Patch -Headers $Headers -Body $Body
    Write-Host "✅ Content Understanding defaults set successfully!" -ForegroundColor Green
    Write-Host "Response: $($Response | ConvertTo-Json -Depth 10)"
}
catch {
    $StatusCode = $_.Exception.Response.StatusCode.value__
    $ErrorMessage = $_.ErrorDetails.Message
    
    Write-Host "❌ Failed to set Content Understanding defaults" -ForegroundColor Red
    Write-Host "HTTP Status: $StatusCode"
    Write-Host "Response: $ErrorMessage"
    exit 1
}
