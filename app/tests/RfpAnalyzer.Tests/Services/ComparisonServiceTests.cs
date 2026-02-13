using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using RfpAnalyzer.Models;
using RfpAnalyzer.Services;

namespace RfpAnalyzer.Tests.Services;

public class ComparisonServiceTests
{
    private readonly ComparisonService _service;

    public ComparisonServiceTests()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/",
                ["AZURE_OPENAI_DEPLOYMENT_NAME"] = "gpt-4o-mini"
            })
            .Build();

        var logger = new Mock<ILogger<ComparisonService>>();
        _service = new ComparisonService(config, logger.Object);
    }

    [Fact]
    public void CleanJsonResponse_RemovesJsonCodeFence()
    {
        var input = "```json\n{\"key\": \"value\"}\n```";
        var result = ComparisonService.CleanJsonResponse(input);
        Assert.Equal("{\"key\": \"value\"}", result);
    }

    [Fact]
    public void CleanJsonResponse_HandlesCleanJson()
    {
        var input = "{\"key\": \"value\"}";
        var result = ComparisonService.CleanJsonResponse(input);
        Assert.Equal("{\"key\": \"value\"}", result);
    }

    [Fact]
    public void GenerateCsvReport_ProducesValidOutput()
    {
        var comparison = new ComparisonResult
        {
            RfpTitle = "Test RFP",
            ComparisonDate = "2025-12-15",
            TotalVendors = 2,
            VendorRankings = new List<VendorRanking>
            {
                new() { Rank = 1, VendorName = "Vendor A", TotalScore = 85.0, Grade = "B", Recommendation = "Recommended" },
                new() { Rank = 2, VendorName = "Vendor B", TotalScore = 72.0, Grade = "C", Recommendation = "Consider" }
            },
            ComparisonInsights = new List<string> { "Vendor A leads in technical areas" },
            SelectionRecommendation = "Select Vendor A"
        };

        var evaluations = new List<EvaluationResult>
        {
            new()
            {
                SupplierName = "Vendor A",
                TotalScore = 85.0,
                CriterionScores = new List<CriterionScore>
                {
                    new() { CriterionName = "Technical", Weight = 50, RawScore = 90, WeightedScore = 45.0 },
                    new() { CriterionName = "Price", Weight = 50, RawScore = 80, WeightedScore = 40.0 }
                }
            },
            new()
            {
                SupplierName = "Vendor B",
                TotalScore = 72.0,
                CriterionScores = new List<CriterionScore>
                {
                    new() { CriterionName = "Technical", Weight = 50, RawScore = 70, WeightedScore = 35.0 },
                    new() { CriterionName = "Price", Weight = 50, RawScore = 74, WeightedScore = 37.0 }
                }
            }
        };

        var csvBytes = _service.GenerateCsvReport(comparison, evaluations);

        Assert.NotNull(csvBytes);
        Assert.True(csvBytes.Length > 0);

        var csvContent = System.Text.Encoding.UTF8.GetString(csvBytes);
        Assert.Contains("Test RFP", csvContent);
        Assert.Contains("Vendor A", csvContent);
        Assert.Contains("Vendor B", csvContent);
        Assert.Contains("VENDOR RANKINGS", csvContent);
        Assert.Contains("CRITERION COMPARISON", csvContent);
        Assert.Contains("Select Vendor A", csvContent);
    }

    [Fact]
    public void GenerateExcelReport_ProducesValidOutput()
    {
        var comparison = new ComparisonResult
        {
            RfpTitle = "Test RFP",
            ComparisonDate = "2025-12-15",
            TotalVendors = 1,
            VendorRankings = new List<VendorRanking>
            {
                new() { Rank = 1, VendorName = "Vendor A", TotalScore = 85.0, Grade = "B", Recommendation = "Select" }
            }
        };

        var evaluations = new List<EvaluationResult>
        {
            new()
            {
                SupplierName = "Vendor A",
                TotalScore = 85.0,
                CriterionScores = new List<CriterionScore>
                {
                    new() { CriterionName = "Quality", Weight = 60, RawScore = 90 },
                    new() { CriterionName = "Price", Weight = 40, RawScore = 78 }
                }
            }
        };

        var excelBytes = _service.GenerateExcelReport(comparison, evaluations);

        Assert.NotNull(excelBytes);
        Assert.True(excelBytes.Length > 0);
    }

    [Fact]
    public void GenerateCsvReport_EmptyEvaluations_ProducesValidOutput()
    {
        var comparison = new ComparisonResult
        {
            RfpTitle = "Empty RFP",
            ComparisonDate = "2025-12-15",
            TotalVendors = 0,
            ComparisonInsights = new List<string>(),
            SelectionRecommendation = "No vendors to compare"
        };

        var csvBytes = _service.GenerateCsvReport(comparison, new List<EvaluationResult>());

        Assert.NotNull(csvBytes);
        var csvContent = System.Text.Encoding.UTF8.GetString(csvBytes);
        Assert.Contains("Empty RFP", csvContent);
        Assert.Contains("No vendors to compare", csvContent);
    }

    [Fact]
    public void GenerateCsvReport_EscapesCsvSpecialCharacters()
    {
        var comparison = new ComparisonResult
        {
            RfpTitle = "Test RFP",
            ComparisonDate = "2025-12-15",
            TotalVendors = 1,
            VendorRankings = new List<VendorRanking>
            {
                new()
                {
                    Rank = 1,
                    VendorName = "Vendor A",
                    TotalScore = 85.0,
                    Grade = "B",
                    Recommendation = "Select \"this\" vendor, definitely"
                }
            },
            ComparisonInsights = new List<string>(),
            SelectionRecommendation = "Go with it"
        };

        var csvBytes = _service.GenerateCsvReport(comparison, new List<EvaluationResult>());
        var csvContent = System.Text.Encoding.UTF8.GetString(csvBytes);

        // Recommendation with commas and quotes should be escaped
        Assert.Contains("\"Select \"\"this\"\" vendor, definitely\"", csvContent);
    }

    [Fact]
    public void CreateComparisonAgent_ThrowsWhenEndpointMissing()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>())
            .Build();
        var logger = new Mock<ILogger<ComparisonService>>();
        var service = new ComparisonService(config, logger.Object);

        Assert.Throws<InvalidOperationException>(() => service.CreateComparisonAgent());
    }

    [Fact]
    public void CreateComparisonAgent_ThrowsWhenDeploymentMissing()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/"
            })
            .Build();
        var logger = new Mock<ILogger<ComparisonService>>();
        var service = new ComparisonService(config, logger.Object);

        Assert.Throws<InvalidOperationException>(() => service.CreateComparisonAgent());
    }

    [Fact]
    public void CreateComparisonAgent_ReturnsAIAgent()
    {
        var agent = _service.CreateComparisonAgent();
        Assert.NotNull(agent);
    }

    [Fact]
    public void CreateComparisonOrchestrator_ReturnsAIAgent()
    {
        var comparisonAgent = _service.CreateComparisonAgent();
        var orchestrator = _service.CreateComparisonOrchestrator(comparisonAgent);
        Assert.NotNull(orchestrator);
    }

    [Fact]
    public void CreateComparisonOrchestrator_ThrowsWhenEndpointMissing()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>())
            .Build();
        var logger = new Mock<ILogger<ComparisonService>>();
        var service = new ComparisonService(config, logger.Object);

        // Create agent with valid config, then try orchestrator with invalid config
        var agent = _service.CreateComparisonAgent();
        Assert.Throws<InvalidOperationException>(() => service.CreateComparisonOrchestrator(agent));
    }
}
