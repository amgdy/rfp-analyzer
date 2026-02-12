namespace EfpAnalyzer.Models;

public class VendorRanking
{
    public int Rank { get; set; }
    public string VendorName { get; set; } = "";
    public double TotalScore { get; set; }
    public string Grade { get; set; } = "";
    public List<string> KeyStrengths { get; set; } = new();
    public List<string> KeyConcerns { get; set; } = new();
    public string Recommendation { get; set; } = "";
}

public class CriterionComparison
{
    public string CriterionId { get; set; } = "";
    public string CriterionName { get; set; } = "";
    public double Weight { get; set; }
    public string BestVendor { get; set; } = "";
    public string WorstVendor { get; set; } = "";
    public string ScoreRange { get; set; } = "";
    public string Insights { get; set; } = "";
}

public class ComparisonResult
{
    public string RfpTitle { get; set; } = "";
    public string ComparisonDate { get; set; } = "";
    public int TotalVendors { get; set; }
    public List<VendorRanking> VendorRankings { get; set; } = new();
    public List<CriterionComparison> CriterionComparisons { get; set; } = new();
    public string WinnerSummary { get; set; } = "";
    public List<string> ComparisonInsights { get; set; } = new();
    public string SelectionRecommendation { get; set; } = "";
    public string RiskComparison { get; set; } = "";
}
