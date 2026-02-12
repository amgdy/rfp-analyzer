using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Azure.Core;
using Azure.Identity;
using EfpAnalyzer.Models;

namespace EfpAnalyzer.Services;

public class DocumentProcessorService
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IConfiguration _configuration;
    private readonly ILogger<DocumentProcessorService> _logger;
    private readonly TokenCredential _credential;

    public DocumentProcessorService(
        IHttpClientFactory httpClientFactory,
        IConfiguration configuration,
        ILogger<DocumentProcessorService> logger)
    {
        _httpClientFactory = httpClientFactory;
        _configuration = configuration;
        _logger = logger;
        _credential = new DefaultAzureCredential();
    }

    public async Task<string> ExtractContentAsync(byte[] fileBytes, string filename, ExtractionService service, CancellationToken ct = default)
    {
        var requestId = Guid.NewGuid().ToString()[..8];
        _logger.LogInformation("[REQ:{RequestId}] Starting content extraction for: {Filename} ({Size} bytes) using {Service}",
            requestId, filename, fileBytes.Length, service);

        var extension = Path.GetExtension(filename).TrimStart('.').ToLowerInvariant();

        // Handle plain text and markdown files directly
        if (extension is "txt" or "md")
        {
            _logger.LogInformation("[REQ:{RequestId}] Processing as plain text/markdown", requestId);
            return Encoding.UTF8.GetString(fileBytes);
        }

        return service switch
        {
            ExtractionService.ContentUnderstanding => await ExtractWithContentUnderstandingAsync(fileBytes, requestId, ct),
            ExtractionService.DocumentIntelligence => await ExtractWithDocumentIntelligenceAsync(fileBytes, requestId, ct),
            _ => throw new ArgumentOutOfRangeException(nameof(service))
        };
    }

    private async Task<string> ExtractWithContentUnderstandingAsync(byte[] fileBytes, string requestId, CancellationToken ct)
    {
        var endpoint = _configuration["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"]
            ?? throw new InvalidOperationException("AZURE_CONTENT_UNDERSTANDING_ENDPOINT is not configured");

        _logger.LogInformation("[REQ:{RequestId}] Processing with Azure Content Understanding...", requestId);

        var client = _httpClientFactory.CreateClient();
        var token = await GetTokenAsync(ct);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        // Step 1: Begin analysis
        var analyzeUrl = $"{endpoint.TrimEnd('/')}/contentunderstanding/analyzers/prebuilt-documentSearch:analyze?api-version=2025-11-01";

        using var content = new ByteArrayContent(fileBytes);
        content.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");

        var response = await client.PostAsync(analyzeUrl, content, ct);
        response.EnsureSuccessStatusCode();

        // Step 2: Poll for result
        var operationLocation = response.Headers.GetValues("Operation-Location").FirstOrDefault()
            ?? throw new InvalidOperationException("No Operation-Location header in response");

        _logger.LogInformation("[REQ:{RequestId}] Polling for analysis result...", requestId);

        string? markdown = null;
        for (int i = 0; i < 120; i++) // Poll for up to 10 minutes
        {
            await Task.Delay(5000, ct);

            var pollClient = _httpClientFactory.CreateClient();
            var pollToken = await GetTokenAsync(ct);
            pollClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", pollToken);

            var pollResponse = await pollClient.GetAsync(operationLocation, ct);
            pollResponse.EnsureSuccessStatusCode();

            var pollJson = await pollResponse.Content.ReadAsStringAsync(ct);
            using var doc = JsonDocument.Parse(pollJson);
            var status = doc.RootElement.GetProperty("status").GetString();

            if (status == "Succeeded" || status == "succeeded")
            {
                if (doc.RootElement.TryGetProperty("result", out var result) &&
                    result.TryGetProperty("contents", out var contents) &&
                    contents.GetArrayLength() > 0)
                {
                    var first = contents[0];
                    if (first.TryGetProperty("markdown", out var md))
                    {
                        markdown = md.GetString() ?? "";
                    }
                }
                break;
            }
            else if (status == "Failed" || status == "failed")
            {
                throw new InvalidOperationException($"Content Understanding analysis failed: {pollJson}");
            }
        }

        _logger.LogInformation("[REQ:{RequestId}] Content Understanding extraction completed ({Chars} chars)", requestId, markdown?.Length ?? 0);
        return markdown ?? "";
    }

    private async Task<string> ExtractWithDocumentIntelligenceAsync(byte[] fileBytes, string requestId, CancellationToken ct)
    {
        var endpoint = _configuration["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"]
            ?? _configuration["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"]
            ?? throw new InvalidOperationException("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not configured");

        _logger.LogInformation("[REQ:{RequestId}] Processing with Azure Document Intelligence...", requestId);

        var client = _httpClientFactory.CreateClient();
        var token = await GetTokenAsync(ct);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        // Step 1: Begin analysis
        var analyzeUrl = $"{endpoint.TrimEnd('/')}/documentintelligence/documentModels/prebuilt-layout:analyze?api-version=2024-11-30&outputContentFormat=markdown";

        using var content = new ByteArrayContent(fileBytes);
        content.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");

        var response = await client.PostAsync(analyzeUrl, content, ct);
        response.EnsureSuccessStatusCode();

        var operationLocation = response.Headers.GetValues("Operation-Location").FirstOrDefault()
            ?? throw new InvalidOperationException("No Operation-Location header in response");

        _logger.LogInformation("[REQ:{RequestId}] Polling for Document Intelligence result...", requestId);

        string? markdown = null;
        for (int i = 0; i < 120; i++)
        {
            await Task.Delay(5000, ct);

            var pollClient = _httpClientFactory.CreateClient();
            var pollToken = await GetTokenAsync(ct);
            pollClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", pollToken);

            var pollResponse = await pollClient.GetAsync(operationLocation, ct);
            pollResponse.EnsureSuccessStatusCode();

            var pollJson = await pollResponse.Content.ReadAsStringAsync(ct);
            using var doc = JsonDocument.Parse(pollJson);
            var status = doc.RootElement.GetProperty("status").GetString();

            if (status == "succeeded")
            {
                if (doc.RootElement.TryGetProperty("analyzeResult", out var analyzeResult) &&
                    analyzeResult.TryGetProperty("content", out var contentProp))
                {
                    markdown = contentProp.GetString() ?? "";
                }
                break;
            }
            else if (status == "failed")
            {
                throw new InvalidOperationException($"Document Intelligence analysis failed: {pollJson}");
            }
        }

        _logger.LogInformation("[REQ:{RequestId}] Document Intelligence extraction completed ({Chars} chars)", requestId, markdown?.Length ?? 0);
        return markdown ?? "";
    }

    private async Task<string> GetTokenAsync(CancellationToken ct)
    {
        var tokenResult = await _credential.GetTokenAsync(
            new TokenRequestContext(new[] { "https://cognitiveservices.azure.com/.default" }), ct);
        return tokenResult.Token;
    }
}
