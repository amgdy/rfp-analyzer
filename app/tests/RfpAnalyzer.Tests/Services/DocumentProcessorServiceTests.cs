using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using RfpAnalyzer.Models;
using RfpAnalyzer.Services;

namespace RfpAnalyzer.Tests.Services;

public class DocumentProcessorServiceTests
{
    private DocumentProcessorService CreateService(Dictionary<string, string?> config)
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(config)
            .Build();
        var logger = new Mock<ILogger<DocumentProcessorService>>();
        var httpClientFactory = new Mock<IHttpClientFactory>();
        httpClientFactory.Setup(f => f.CreateClient(It.IsAny<string>())).Returns(new HttpClient());
        return new DocumentProcessorService(httpClientFactory.Object, configuration, logger.Object);
    }

    [Fact]
    public async Task ExtractContentAsync_PlainText_ReturnsContentDirectly()
    {
        var service = CreateService(new Dictionary<string, string?>());
        var content = "Hello, World!"u8.ToArray();

        var result = await service.ExtractContentAsync(content, "test.txt", ExtractionService.ContentUnderstanding);

        Assert.Equal("Hello, World!", result);
    }

    [Fact]
    public async Task ExtractContentAsync_Markdown_ReturnsContentDirectly()
    {
        var service = CreateService(new Dictionary<string, string?>());
        var content = "# Heading\n\nSome content"u8.ToArray();

        var result = await service.ExtractContentAsync(content, "test.md", ExtractionService.DocumentIntelligence);

        Assert.Equal("# Heading\n\nSome content", result);
    }

    [Fact]
    public async Task ExtractContentAsync_DocumentIntelligence_ThrowsWhenEndpointMissing()
    {
        var service = CreateService(new Dictionary<string, string?>());
        var content = new byte[] { 1, 2, 3 };

        await Assert.ThrowsAsync<InvalidOperationException>(
            () => service.ExtractContentAsync(content, "test.pdf", ExtractionService.DocumentIntelligence));
    }

    [Fact]
    public async Task ExtractContentAsync_ContentUnderstanding_ThrowsWhenEndpointMissing()
    {
        var service = CreateService(new Dictionary<string, string?>());
        var content = new byte[] { 1, 2, 3 };

        await Assert.ThrowsAsync<InvalidOperationException>(
            () => service.ExtractContentAsync(content, "test.pdf", ExtractionService.ContentUnderstanding));
    }

    [Fact]
    public async Task ExtractContentAsync_InvalidService_ThrowsArgumentOutOfRange()
    {
        var service = CreateService(new Dictionary<string, string?>());
        var content = new byte[] { 1, 2, 3 };

        await Assert.ThrowsAsync<ArgumentOutOfRangeException>(
            () => service.ExtractContentAsync(content, "test.pdf", (ExtractionService)999));
    }

    [Theory]
    [InlineData("test.txt")]
    [InlineData("README.md")]
    [InlineData("notes.TXT")]
    [InlineData("doc.MD")]
    public async Task ExtractContentAsync_TextExtensions_SkipsAzureService(string filename)
    {
        var service = CreateService(new Dictionary<string, string?>());
        var content = "plain text content"u8.ToArray();

        // Should not throw even without endpoint configured, because text files bypass Azure services
        var result = await service.ExtractContentAsync(content, filename, ExtractionService.DocumentIntelligence);

        Assert.Equal("plain text content", result);
    }

    [Fact]
    public async Task ExtractContentAsync_DocumentIntelligence_FallsBackToContentUnderstandingEndpoint()
    {
        // When AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not set but
        // AZURE_CONTENT_UNDERSTANDING_ENDPOINT is, it should use the fallback.
        // We can't fully test the SDK call without a real endpoint, but we can verify
        // the configuration fallback doesn't throw InvalidOperationException for missing endpoint.
        var service = CreateService(new Dictionary<string, string?>
        {
            ["AZURE_CONTENT_UNDERSTANDING_ENDPOINT"] = "https://test.cognitiveservices.azure.com/"
        });

        // This will fail with an auth/network error (not a config error), proving fallback works
        var ex = await Assert.ThrowsAnyAsync<Exception>(
            () => service.ExtractContentAsync(new byte[] { 1, 2, 3 }, "test.pdf", ExtractionService.DocumentIntelligence));

        // Should NOT be InvalidOperationException about missing config
        Assert.IsNotType<InvalidOperationException>(ex);
    }
}
