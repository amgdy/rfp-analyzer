namespace EfpAnalyzer.Models;

public class EvaluationResult
{
    public string RfpTitle { get; set; } = "";
    public string SupplierName { get; set; } = "";
    public string SupplierSite { get; set; } = "";
    public string ResponseId { get; set; } = "";
    public double TotalScore { get; set; }
    public double ScorePercentage { get; set; }
    public string Grade { get; set; } = "";
    public string Recommendation { get; set; } = "";
    public ExtractedCriteria? ExtractedCriteria { get; set; }
    public List<CriterionScore> CriterionScores { get; set; } = new();
    public string ExecutiveSummary { get; set; } = "";
    public List<string> OverallStrengths { get; set; } = new();
    public List<string> OverallWeaknesses { get; set; } = new();
    public List<string> Recommendations { get; set; } = new();
    public string RiskAssessment { get; set; } = "";
    public EvaluationMetadata? Metadata { get; set; }
}

public class EvaluationMetadata
{
    public string Version { get; set; } = "2.0";
    public string EvaluationType { get; set; } = "multi-agent";
    public string EvaluationTimestamp { get; set; } = "";
    public double TotalDurationSeconds { get; set; }
    public double Phase1CriteriaExtractionSeconds { get; set; }
    public double Phase2ProposalScoringSeconds { get; set; }
    public int CriteriaCount { get; set; }
    public string ModelDeployment { get; set; } = "";
    public string ReasoningEffort { get; set; } = "";
}

public enum ExtractionService
{
    ContentUnderstanding,
    DocumentIntelligence
}

public class UploadedDocument
{
    public string FileName { get; set; } = "";
    public byte[] Content { get; set; } = Array.Empty<byte>();
    public long Size { get; set; }
    public string? ExtractedContent { get; set; }
    public bool IsExtracted { get; set; }
}

public class AppState
{
    public UploadedDocument? RfpDocument { get; set; }
    public List<UploadedDocument> ProposalDocuments { get; set; } = new();
    public ExtractionService SelectedService { get; set; } = ExtractionService.ContentUnderstanding;
    public string ReasoningEffort { get; set; } = "high";
    public string CustomCriteria { get; set; } = "";
    public Dictionary<string, EvaluationResult> EvaluationResults { get; set; } = new();
    public ComparisonResult? ComparisonResult { get; set; }
    public ProcessingQueue ExtractionQueue { get; set; } = new() { Name = "Extraction" };
    public ProcessingQueue EvaluationQueue { get; set; } = new() { Name = "Evaluation" };
    public int CurrentStep { get; set; } = 0; // 0=landing, 1=upload, 2=extract, 3=evaluate
}
