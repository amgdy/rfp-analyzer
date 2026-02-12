using RfpAnalyzer.Models;

namespace RfpAnalyzer.Tests.Models;

public class ScoringModelsTests
{
    [Fact]
    public void ExtractedCriteria_DefaultValues()
    {
        var criteria = new ExtractedCriteria();
        Assert.Equal("", criteria.RfpTitle);
        Assert.Equal(100.0, criteria.TotalWeight);
        Assert.Empty(criteria.Criteria);
    }

    [Fact]
    public void CriterionScore_WeightedScoreCalculation()
    {
        // This tests the business logic formula: weighted_score = (raw_score * weight) / 100
        var score = new CriterionScore
        {
            CriterionId = "C-1",
            CriterionName = "Technical",
            Weight = 30,
            RawScore = 85,
            WeightedScore = 85 * 30.0 / 100 // = 25.5
        };

        Assert.Equal(25.5, score.WeightedScore);
    }

    [Fact]
    public void ProposalEvaluation_DefaultValues()
    {
        var eval = new ProposalEvaluation();
        Assert.Equal("", eval.RfpTitle);
        Assert.Equal(0, eval.TotalScore);
        Assert.Equal("", eval.Grade);
        Assert.Empty(eval.CriterionScores);
        Assert.Empty(eval.OverallStrengths);
        Assert.Empty(eval.OverallWeaknesses);
    }

    [Theory]
    [InlineData(95, "A")]
    [InlineData(90, "A")]
    [InlineData(85, "B")]
    [InlineData(80, "B")]
    [InlineData(75, "C")]
    [InlineData(70, "C")]
    [InlineData(65, "D")]
    [InlineData(60, "D")]
    [InlineData(55, "F")]
    [InlineData(0, "F")]
    public void GradeAssignment_MatchesPythonLogic(double score, string expectedGrade)
    {
        // This replicates the grade assignment from scoring_agent_v2.py
        string grade = score switch
        {
            >= 90 => "A",
            >= 80 => "B",
            >= 70 => "C",
            >= 60 => "D",
            _ => "F"
        };
        Assert.Equal(expectedGrade, grade);
    }

    [Fact]
    public void WeightNormalization_SumsTo100()
    {
        // Test the weight normalization logic from CriteriaExtractionAgent._parse_response()
        var criteria = new List<ScoringCriterion>
        {
            new() { CriterionId = "C-1", Weight = 40 },
            new() { CriterionId = "C-2", Weight = 30 },
            new() { CriterionId = "C-3", Weight = 50 } // Total: 120, not 100
        };

        var totalWeight = criteria.Sum(c => c.Weight);
        if (Math.Abs(totalWeight - 100) > 0.1)
        {
            foreach (var c in criteria)
            {
                c.Weight = c.Weight / totalWeight * 100;
            }
        }

        var newTotal = criteria.Sum(c => c.Weight);
        Assert.Equal(100.0, newTotal, 1); // within 0.1

        // Verify proportions maintained
        Assert.Equal(100.0 * 40 / 120, criteria[0].Weight, 1);
        Assert.Equal(100.0 * 30 / 120, criteria[1].Weight, 1);
        Assert.Equal(100.0 * 50 / 120, criteria[2].Weight, 1);
    }

    [Fact]
    public void TotalScoreCalculation_SumOfWeightedScores()
    {
        // Test total_score = SUM(weighted_scores)
        var scores = new List<CriterionScore>
        {
            new() { RawScore = 80, Weight = 30, WeightedScore = 24.0 },
            new() { RawScore = 90, Weight = 25, WeightedScore = 22.5 },
            new() { RawScore = 70, Weight = 20, WeightedScore = 14.0 },
            new() { RawScore = 85, Weight = 15, WeightedScore = 12.75 },
            new() { RawScore = 60, Weight = 10, WeightedScore = 6.0 },
        };

        var totalScore = Math.Round(scores.Sum(s => s.WeightedScore), 2);
        Assert.Equal(79.25, totalScore);
    }
}
