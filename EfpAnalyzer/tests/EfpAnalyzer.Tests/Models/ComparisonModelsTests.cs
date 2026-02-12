using EfpAnalyzer.Models;

namespace EfpAnalyzer.Tests.Models;

public class ComparisonModelsTests
{
    [Fact]
    public void ComparisonResult_DefaultValues()
    {
        var result = new ComparisonResult();
        Assert.Equal("", result.RfpTitle);
        Assert.Equal(0, result.TotalVendors);
        Assert.Empty(result.VendorRankings);
        Assert.Empty(result.CriterionComparisons);
        Assert.Empty(result.ComparisonInsights);
    }

    [Fact]
    public void VendorRanking_DefaultValues()
    {
        var ranking = new VendorRanking();
        Assert.Equal(0, ranking.Rank);
        Assert.Equal("", ranking.VendorName);
        Assert.Equal(0, ranking.TotalScore);
        Assert.Empty(ranking.KeyStrengths);
        Assert.Empty(ranking.KeyConcerns);
    }

    [Fact]
    public void CriterionComparison_DefaultValues()
    {
        var comp = new CriterionComparison();
        Assert.Equal("", comp.CriterionId);
        Assert.Equal("", comp.BestVendor);
        Assert.Equal("", comp.WorstVendor);
        Assert.Equal(0, comp.Weight);
    }
}
