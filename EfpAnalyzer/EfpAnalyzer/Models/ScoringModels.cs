namespace EfpAnalyzer.Models;

// Maps from Python's ScoringCriterion
public class ScoringCriterion
{
    public string CriterionId { get; set; } = "";
    public string Name { get; set; } = "";
    public string Description { get; set; } = "";
    public string Category { get; set; } = "";
    public double Weight { get; set; }
    public int MaxScore { get; set; } = 100;
    public string EvaluationGuidance { get; set; } = "";
}

// Maps from Python's ExtractedCriteria
public class ExtractedCriteria
{
    public string RfpTitle { get; set; } = "";
    public string RfpSummary { get; set; } = "";
    public double TotalWeight { get; set; } = 100.0;
    public List<ScoringCriterion> Criteria { get; set; } = new();
    public string ExtractionNotes { get; set; } = "";
}

// Maps from Python's CriterionScore
public class CriterionScore
{
    public string CriterionId { get; set; } = "";
    public string CriterionName { get; set; } = "";
    public double Weight { get; set; }
    public double RawScore { get; set; }
    public double WeightedScore { get; set; }
    public string Evidence { get; set; } = "";
    public string Justification { get; set; } = "";
    public List<string> Strengths { get; set; } = new();
    public List<string> Gaps { get; set; } = new();
}

// Maps from Python's ProposalEvaluationV2
public class ProposalEvaluation
{
    public string RfpTitle { get; set; } = "";
    public string SupplierName { get; set; } = "";
    public string SupplierSite { get; set; } = "";
    public string ResponseId { get; set; } = "";
    public string EvaluationDate { get; set; } = "";
    public double TotalScore { get; set; }
    public double ScorePercentage { get; set; }
    public string Grade { get; set; } = "";
    public string Recommendation { get; set; } = "";
    public List<CriterionScore> CriterionScores { get; set; } = new();
    public string ExecutiveSummary { get; set; } = "";
    public List<string> OverallStrengths { get; set; } = new();
    public List<string> OverallWeaknesses { get; set; } = new();
    public List<string> Recommendations { get; set; } = new();
    public string RiskAssessment { get; set; } = "";
}
