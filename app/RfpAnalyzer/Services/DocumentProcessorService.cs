using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Azure;
using Azure.AI.DocumentIntelligence;
using Azure.Core;
using Azure.Identity;
using RfpAnalyzer.Models;

namespace RfpAnalyzer.Services;

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
            ExtractionService.ContentUnderstanding => await ExtractWithContentUnderstandingAsync(fileBytes, filename, requestId, ct),
            ExtractionService.DocumentIntelligence => await ExtractWithDocumentIntelligenceAsync(fileBytes, requestId, ct),
            _ => throw new ArgumentOutOfRangeException(nameof(service))
        };
    }

    /// <summary>
    /// Maps a file extension to the corresponding MIME type for Content Understanding.
    /// </summary>
    private static string GetMimeType(string filename)
    {
        var ext = Path.GetExtension(filename).ToLowerInvariant();
        return ext switch
        {
            ".pdf" => "application/pdf",
            ".docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc" => "application/msword",
            ".pptx" => "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".ppt" => "application/vnd.ms-powerpoint",
            ".xlsx" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls" => "application/vnd.ms-excel",
            ".png" => "image/png",
            ".jpg" or ".jpeg" => "image/jpeg",
            ".tiff" or ".tif" => "image/tiff",
            ".bmp" => "image/bmp",
            ".html" or ".htm" => "text/html",
            _ => "application/octet-stream"
        };
    }

    private async Task<string> ExtractWithContentUnderstandingAsync(byte[] fileBytes, string filename, string requestId, CancellationToken ct)
    {
        var endpoint = _configuration["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"];
        if (string.IsNullOrWhiteSpace(endpoint))
            throw new InvalidOperationException("AZURE_CONTENT_UNDERSTANDING_ENDPOINT is not configured. Set it in appsettings.json, appsettings.Development.json, or as an environment variable.");

        _logger.LogInformation("[REQ:{RequestId}] Processing with Azure Content Understanding...", requestId);

        var client = _httpClientFactory.CreateClient();
        var token = await GetTokenAsync(ct);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        // Step 1: Begin analysis — send as JSON with base64 data URI
        var analyzeUrl = $"{endpoint.TrimEnd('/')}/contentunderstanding/analyzers/prebuilt-read:analyze?api-version=2024-12-01-preview";

        var mimeType = GetMimeType(filename);
        var base64Content = Convert.ToBase64String(fileBytes);
        var dataUri = $"data:{mimeType};base64,{base64Content}";

        var requestBody = JsonSerializer.Serialize(new { url = dataUri });
        using var content = new StringContent(requestBody, Encoding.UTF8, "application/json");

        var response = await client.PostAsync(analyzeUrl, content, ct);
        if (!response.IsSuccessStatusCode)
        {
            var errorBody = await response.Content.ReadAsStringAsync(ct);
            _logger.LogError("[REQ:{RequestId}] Content Understanding returned {StatusCode}: {Error}", requestId, response.StatusCode, errorBody);
            throw new HttpRequestException($"Content Understanding analysis failed ({response.StatusCode}): {errorBody}");
        }

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

    /// <summary>
    /// Extracts document content using the official Azure.AI.DocumentIntelligence SDK.
    /// Uses the prebuilt-layout model with markdown output format.
    /// Authentication via DefaultAzureCredential (Managed Identity in Azure, az login locally).
    /// </summary>
    private async Task<string> ExtractWithDocumentIntelligenceAsync(byte[] fileBytes, string requestId, CancellationToken ct)
    {
        var endpoint = _configuration["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"];
        if (string.IsNullOrWhiteSpace(endpoint))
            endpoint = _configuration["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"];
        if (string.IsNullOrWhiteSpace(endpoint))
            throw new InvalidOperationException("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not configured. Set it in appsettings.json, appsettings.Development.json, or as an environment variable.");

        _logger.LogInformation("[REQ:{RequestId}] Processing with Azure Document Intelligence SDK...", requestId);

        var client = new DocumentIntelligenceClient(new Uri(endpoint), _credential);

        var analyzeOptions = new AnalyzeDocumentOptions("prebuilt-layout", BinaryData.FromBytes(fileBytes))
        {
            OutputContentFormat = DocumentContentFormat.Markdown
        };

        _logger.LogInformation("[REQ:{RequestId}] Starting document analysis (prebuilt-layout, markdown output)...", requestId);
        var operation = await client.AnalyzeDocumentAsync(WaitUntil.Completed, analyzeOptions, ct);
        var result = operation.Value;

        var content = result.Content ?? "";
        _logger.LogInformation("[REQ:{RequestId}] Document Intelligence extraction completed ({Chars} chars)", requestId, content.Length);
        return content;
    }

    private async Task<string> GetTokenAsync(CancellationToken ct)
    {
        var tokenResult = await _credential.GetTokenAsync(
            new TokenRequestContext(new[] { "https://cognitiveservices.azure.com/.default" }), ct);
        return tokenResult.Token;
    }
}
