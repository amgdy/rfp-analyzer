#!/bin/bash

# Post-provision hook to set Content Understanding defaults
# This script is executed by Azure Developer CLI after provisioning

set -e

# Ask the user if they want to set Content Understanding defaults
echo ""
echo "=========================================="
echo " Content Understanding Configuration"
echo "=========================================="
echo ""
echo "This step configures the default model deployments for Azure Content Understanding."
echo "Models: gpt-4.1, gpt-4.1-mini, text-embedding-3-large"
echo ""
read -r -p "Do you want to set Content Understanding defaults? (y/N): " REPLY
echo ""

if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "⏭️  Skipping Content Understanding defaults configuration."
    exit 0
fi

echo "Setting Content Understanding defaults..."

# Get the Content Understanding endpoint from azd env
CONTENT_UNDERSTANDING_ENDPOINT=$(azd env get-value AZURE_CONTENT_UNDERSTANDING_ENDPOINT 2>/dev/null || echo "")

if [ -z "$CONTENT_UNDERSTANDING_ENDPOINT" ]; then
    echo "Error: AZURE_CONTENT_UNDERSTANDING_ENDPOINT not found in azd environment"
    exit 1
fi

echo "Content Understanding Endpoint: $CONTENT_UNDERSTANDING_ENDPOINT"

# Get access token for Azure Cognitive Services
echo "Obtaining access token..."
ACCESS_TOKEN=$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)

if [ -z "$ACCESS_TOKEN" ]; then
    echo "Error: Failed to obtain access token"
    exit 1
fi

# Set the default model deployments for Content Understanding
API_URL="${CONTENT_UNDERSTANDING_ENDPOINT}contentunderstanding/defaults?api-version=2025-11-01"

echo "Calling Content Understanding API to set defaults..."
echo "URL: $API_URL"

RESPONSE=$(curl -s -w "\n%{http_code}" -X PATCH "$API_URL" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "modelDeployments": {
            "gpt-4.1": "gpt-4.1",
            "gpt-4.1-mini": "gpt-4.1-mini",
            "text-embedding-3-large": "text-embedding-3-large"
        }
    }')

# Extract HTTP status code (last line)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
# Extract response body (all but last line)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "✅ Content Understanding defaults set successfully!"
    echo "Response: $BODY"
else
    echo "❌ Failed to set Content Understanding defaults"
    echo "HTTP Status: $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi
