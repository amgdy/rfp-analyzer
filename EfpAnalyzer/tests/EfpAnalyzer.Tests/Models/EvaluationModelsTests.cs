using EfpAnalyzer.Models;

namespace EfpAnalyzer.Tests.Models;

public class EvaluationModelsTests
{
    [Fact]
    public void EvaluationResult_DefaultValues()
    {
        var result = new EvaluationResult();
        Assert.Equal("", result.RfpTitle);
        Assert.Equal("", result.SupplierName);
        Assert.Equal(0, result.TotalScore);
        Assert.Empty(result.CriterionScores);
        Assert.Null(result.Metadata);
    }

    [Fact]
    public void UploadedDocument_DefaultValues()
    {
        var doc = new UploadedDocument();
        Assert.Equal("", doc.FileName);
        Assert.Empty(doc.Content);
        Assert.False(doc.IsExtracted);
        Assert.Null(doc.ExtractedContent);
    }

    [Fact]
    public void AppState_DefaultValues()
    {
        var state = new AppState();
        Assert.Null(state.RfpDocument);
        Assert.Empty(state.ProposalDocuments);
        Assert.Equal(ExtractionService.ContentUnderstanding, state.SelectedService);
        Assert.Equal("high", state.ReasoningEffort);
        Assert.Empty(state.EvaluationResults);
        Assert.Null(state.ComparisonResult);
        Assert.Equal(0, state.CurrentStep);
    }

    [Fact]
    public void EvaluationMetadata_DefaultValues()
    {
        var meta = new EvaluationMetadata();
        Assert.Equal("2.0", meta.Version);
        Assert.Equal("multi-agent", meta.EvaluationType);
        Assert.Equal(0, meta.TotalDurationSeconds);
    }
}
