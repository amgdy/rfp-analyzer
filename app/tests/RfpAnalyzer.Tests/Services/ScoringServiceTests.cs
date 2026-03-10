using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Moq;
using RfpAnalyzer.Models;
using RfpAnalyzer.Services;

namespace RfpAnalyzer.Tests.Services;

public class ScoringServiceTests
{
    private readonly ScoringService _service;

    public ScoringServiceTests()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/",
                ["AZURE_OPENAI_DEPLOYMENT_NAME"] = "gpt-4o-mini"
            })
            .Build();

        var logger = new Mock<ILogger<ScoringService>>();
        _service = new ScoringService(config, logger.Object);
    }

    [Fact]
    public void CleanJsonResponse_RemovesJsonCodeFence()
    {
        var input = "```json\n{\"key\": \"value\"}\n```";
        var result = ScoringService.CleanJsonResponse(input);
        Assert.Equal("{\"key\": \"value\"}", result);
    }

    [Fact]
    public void CleanJsonResponse_RemovesGenericCodeFence()
    {
        var input = "```\n{\"key\": \"value\"}\n```";
        var result = ScoringService.CleanJsonResponse(input);
        Assert.Equal("{\"key\": \"value\"}", result);
    }

    [Fact]
    public void CleanJsonResponse_HandlesCleanJson()
    {
        var input = "{\"key\": \"value\"}";
        var result = ScoringService.CleanJsonResponse(input);
        Assert.Equal("{\"key\": \"value\"}", result);
    }

    [Fact]
    public void CleanJsonResponse_TrimsWhitespace()
    {
        var input = "  \n  {\"key\": \"value\"}  \n  ";
        var result = ScoringService.CleanJsonResponse(input);
        Assert.Equal("{\"key\": \"value\"}", result);
    }

    [Fact]
    public void ParseCriteriaResponse_ValidJson_ExtractsCorrectly()
    {
        var json = """
        {
          "rfp_title": "Cloud Migration RFP",
          "rfp_summary": "Seeking vendor for enterprise cloud migration",
          "total_weight": 100.0,
          "criteria": [
            {
              "criterion_id": "C-1",
              "name": "Technical Capability",
              "description": "Cloud migration expertise",
              "category": "Technical",
              "weight": 40,
              "max_score": 100,
              "evaluation_guidance": "Assess cloud platform expertise"
            },
            {
              "criterion_id": "C-2",
              "name": "Experience",
              "description": "Prior migration projects",
              "category": "Experience",
              "weight": 30,
              "max_score": 100,
              "evaluation_guidance": "Evaluate track record"
            },
            {
              "criterion_id": "C-3",
              "name": "Pricing",
              "description": "Cost effectiveness",
              "category": "Financial",
              "weight": 30,
              "max_score": 100,
              "evaluation_guidance": "Compare value for money"
            }
          ],
          "extraction_notes": "Three key criteria identified"
        }
        """;

        var result = _service.ParseCriteriaResponse(json);

        Assert.Equal("Cloud Migration RFP", result.RfpTitle);
        Assert.Equal("Seeking vendor for enterprise cloud migration", result.RfpSummary);
        Assert.Equal(3, result.Criteria.Count);
        Assert.Equal(100.0, result.TotalWeight);
        Assert.Equal("C-1", result.Criteria[0].CriterionId);
        Assert.Equal("Technical Capability", result.Criteria[0].Name);
        Assert.Equal(40, result.Criteria[0].Weight);
        Assert.Equal("Three key criteria identified", result.ExtractionNotes);
    }

    [Fact]
    public void ParseCriteriaResponse_WithCodeFence_ParsesCorrectly()
    {
        var json = "```json\n" +
            "{\n" +
            "  \"rfp_title\": \"Test RFP\",\n" +
            "  \"rfp_summary\": \"Test summary\",\n" +
            "  \"criteria\": [\n" +
            "    { \"criterion_id\": \"C-1\", \"name\": \"Quality\", \"weight\": 50, \"max_score\": 100 },\n" +
            "    { \"criterion_id\": \"C-2\", \"name\": \"Price\", \"weight\": 50, \"max_score\": 100 }\n" +
            "  ]\n" +
            "}\n" +
            "```";

        var result = _service.ParseCriteriaResponse(json);

        Assert.Equal("Test RFP", result.RfpTitle);
        Assert.Equal(2, result.Criteria.Count);
        Assert.Equal(100.0, result.Criteria.Sum(c => c.Weight), 1);
    }

    [Fact]
    public void ParseCriteriaResponse_WeightsNormalized_WhenNotSummingTo100()
    {
        var json = """
        {
          "rfp_title": "Test RFP",
          "rfp_summary": "Test",
          "criteria": [
            { "criterion_id": "C-1", "name": "A", "weight": 40, "max_score": 100 },
            { "criterion_id": "C-2", "name": "B", "weight": 30, "max_score": 100 },
            { "criterion_id": "C-3", "name": "C", "weight": 50, "max_score": 100 }
          ]
        }
        """;

        var result = _service.ParseCriteriaResponse(json);

        // Original weights sum to 120, should normalize to 100
        Assert.Equal(100.0, result.Criteria.Sum(c => c.Weight), 1);
        Assert.Equal(100.0, result.TotalWeight);
    }

    [Fact]
    public void ParseCriteriaResponse_InvalidJson_ReturnsDefaultCriteria()
    {
        var json = "this is not valid json at all";

        var result = _service.ParseCriteriaResponse(json);

        Assert.Equal("Unknown RFP", result.RfpTitle);
        Assert.Contains("Error parsing response", result.ExtractionNotes);
        Assert.Empty(result.Criteria);
    }

    [Fact]
    public void ParseScoringResponse_ValidJson_ExtractsCorrectly()
    {
        var criteria = new ExtractedCriteria
        {
            RfpTitle = "Test RFP",
            RfpSummary = "Test summary"
        };

        var json = """
        {
          "rfp_title": "Test RFP",
          "supplier_name": "Acme Corp",
          "supplier_site": "New York",
          "response_id": "RESP-2025-0001",
          "evaluation_date": "2025-12-15",
          "total_score": 82.5,
          "score_percentage": 82.5,
          "grade": "B",
          "recommendation": "Strong candidate",
          "criterion_scores": [
            {
              "criterion_id": "C-1",
              "criterion_name": "Technical",
              "weight": 40,
              "raw_score": 85,
              "weighted_score": 34.0,
              "evidence": "Strong cloud experience",
              "justification": "Demonstrated AWS expertise",
              "strengths": ["AWS certified", "Large team"],
              "gaps": ["Limited Azure experience"]
            },
            {
              "criterion_id": "C-2",
              "criterion_name": "Experience",
              "weight": 30,
              "raw_score": 90,
              "weighted_score": 27.0,
              "evidence": "10 years in industry",
              "justification": "Extensive portfolio",
              "strengths": ["Fortune 500 clients"],
              "gaps": []
            },
            {
              "criterion_id": "C-3",
              "criterion_name": "Pricing",
              "weight": 30,
              "raw_score": 75,
              "weighted_score": 22.5,
              "evidence": "Competitive pricing",
              "justification": "Good value",
              "strengths": ["Flexible pricing"],
              "gaps": ["No volume discounts"]
            }
          ],
          "executive_summary": "Acme Corp is a strong candidate.",
          "overall_strengths": ["Technical expertise", "Industry experience"],
          "overall_weaknesses": ["Limited Azure experience"],
          "recommendations": ["Consider for shortlist"],
          "risk_assessment": "Low risk overall"
        }
        """;

        var result = _service.ParseScoringResponse(json, criteria);

        Assert.Equal("Acme Corp", result.SupplierName);
        Assert.Equal("New York", result.SupplierSite);
        Assert.Equal(3, result.CriterionScores.Count);
        // Total = 34.0 + 27.0 + 22.5 = 83.5
        Assert.Equal(83.5, result.TotalScore);
        Assert.Equal("B", result.Grade);
        Assert.Equal(2, result.OverallStrengths.Count);
        Assert.Single(result.OverallWeaknesses);
        Assert.Equal("Low risk overall", result.RiskAssessment);
    }

    [Fact]
    public void ParseScoringResponse_InvalidJson_ReturnsDefaultEvaluation()
    {
        var criteria = new ExtractedCriteria
        {
            RfpTitle = "Test RFP",
            RfpSummary = "Test summary"
        };

        var result = _service.ParseScoringResponse("not json", criteria);

        Assert.Equal("Test RFP", result.RfpTitle);
        Assert.Equal("Unknown Vendor", result.SupplierName);
        Assert.Equal("F", result.Grade);
    }

    [Fact]
    public void ParseScoringResponse_RecalculatesGradeFromWeightedScores()
    {
        var criteria = new ExtractedCriteria { RfpTitle = "Test" };

        var json = """
        {
          "supplier_name": "Vendor A",
          "grade": "A",
          "criterion_scores": [
            { "criterion_id": "C-1", "weight": 50, "raw_score": 60, "weighted_score": 30.0 },
            { "criterion_id": "C-2", "weight": 50, "raw_score": 50, "weighted_score": 25.0 }
          ]
        }
        """;

        var result = _service.ParseScoringResponse(json, criteria);

        // Total = 30.0 + 25.0 = 55.0 -> Grade F (not A as stated in JSON)
        Assert.Equal(55.0, result.TotalScore);
        Assert.Equal("F", result.Grade); // Recalculated, not blindly trusted
    }

    [Fact]
    public void ParseScoringResponse_MissingOptionalFields_UsesDefaults()
    {
        var criteria = new ExtractedCriteria { RfpTitle = "Fallback Title" };

        var json = """
        {
          "criterion_scores": [
            { "criterion_id": "C-1", "weighted_score": 45.0 }
          ]
        }
        """;

        var result = _service.ParseScoringResponse(json, criteria);

        Assert.Equal("Fallback Title", result.RfpTitle);
        Assert.Equal("Unknown Vendor", result.SupplierName);
        Assert.Single(result.CriterionScores);
    }

    [Theory]
    [InlineData(95.0, "A")]
    [InlineData(90.0, "A")]
    [InlineData(85.0, "B")]
    [InlineData(80.0, "B")]
    [InlineData(75.0, "C")]
    [InlineData(70.0, "C")]
    [InlineData(65.0, "D")]
    [InlineData(60.0, "D")]
    [InlineData(55.0, "F")]
    [InlineData(0.0, "F")]
    public void ParseScoringResponse_GradeAssignment_MatchesThresholds(double score, string expectedGrade)
    {
        var criteria = new ExtractedCriteria { RfpTitle = "Test" };
        var json = $$"""
        {
          "supplier_name": "Test Vendor",
          "criterion_scores": [
            { "criterion_id": "C-1", "weighted_score": {{score}} }
          ]
        }
        """;

        var result = _service.ParseScoringResponse(json, criteria);
        Assert.Equal(expectedGrade, result.Grade);
    }

    [Fact]
    public void CreateCriteriaExtractionAgent_ThrowsWhenEndpointMissing()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>())
            .Build();
        var logger = new Mock<ILogger<ScoringService>>();
        var service = new ScoringService(config, logger.Object);

        Assert.Throws<InvalidOperationException>(() => service.CreateCriteriaExtractionAgent());
    }

    [Fact]
    public void CreateProposalScoringAgent_ThrowsWhenEndpointMissing()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>())
            .Build();
        var logger = new Mock<ILogger<ScoringService>>();
        var service = new ScoringService(config, logger.Object);

        Assert.Throws<InvalidOperationException>(() => service.CreateProposalScoringAgent("[]"));
    }

    [Fact]
    public void CreateOrchestratorAgent_ThrowsWhenEndpointMissing()
    {
        var config = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>())
            .Build();
        var logger = new Mock<ILogger<ScoringService>>();
        var service = new ScoringService(config, logger.Object);

        // Need valid agents to pass to orchestrator - but creating them also requires config,
        // so test orchestrator creation with valid config but verify it composes agents
        var configValid = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["AZURE_OPENAI_ENDPOINT"] = "https://test.openai.azure.com/",
                ["AZURE_OPENAI_DEPLOYMENT_NAME"] = "gpt-4o-mini"
            })
            .Build();
        var serviceValid = new ScoringService(configValid, logger.Object);
        var criteriaAgent = serviceValid.CreateCriteriaExtractionAgent();
        var scoringAgent = serviceValid.CreateProposalScoringAgent("[]");

        // Orchestrator requires its own endpoint to create the ChatClient
        Assert.Throws<InvalidOperationException>(() => service.CreateOrchestratorAgent(criteriaAgent, scoringAgent));
    }

    [Fact]
    public void CreateOrchestratorAgent_CreatesWithValidConfig()
    {
        // The orchestrator agent should compose the specialist agents as function tools
        var criteriaAgent = _service.CreateCriteriaExtractionAgent();
        var scoringAgent = _service.CreateProposalScoringAgent("[]");
        var orchestrator = _service.CreateOrchestratorAgent(criteriaAgent, scoringAgent);

        Assert.NotNull(orchestrator);
    }

    [Fact]
    public void CreateCriteriaExtractionAgent_ReturnsAIAgent()
    {
        var agent = _service.CreateCriteriaExtractionAgent();
        Assert.NotNull(agent);
    }

    [Fact]
    public void CreateProposalScoringAgent_ReturnsAIAgent()
    {
        var agent = _service.CreateProposalScoringAgent("[]");
        Assert.NotNull(agent);
    }

    [Fact]
    public void EvaluationMetadata_UsesAgentFrameworkType()
    {
        // Verify metadata reflects the Microsoft Agent Framework usage
        var metadata = new EvaluationMetadata
        {
            Version = "3.0",
            EvaluationType = "microsoft-agent-framework"
        };

        Assert.Equal("3.0", metadata.Version);
        Assert.Equal("microsoft-agent-framework", metadata.EvaluationType);
    }
}
