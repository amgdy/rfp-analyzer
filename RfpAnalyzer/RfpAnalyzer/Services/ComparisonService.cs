using System.Globalization;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Azure.Core;
using Azure.Identity;
using ClosedXML.Excel;
using RfpAnalyzer.Models;

namespace RfpAnalyzer.Services;

public class ComparisonService
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IConfiguration _configuration;
    private readonly ILogger<ComparisonService> _logger;
    private readonly TokenCredential _credential;

    private const string ComparisonInstructions = """
        You are an expert procurement analyst specializing in vendor comparison and selection.

        Your task is to analyze evaluation results from multiple vendors responding to the same RFP
        and provide a comprehensive comparative analysis.

        ## YOUR RESPONSIBILITIES:

        1. **Rank Vendors**: Order vendors by total score, identifying the best performer
        2. **Compare by Criterion**: Analyze how vendors performed on each evaluation criterion
        3. **Identify Patterns**: Find strengths and weaknesses across the vendor pool
        4. **Provide Insights**: Offer actionable insights for the selection committee
        5. **Make Recommendations**: Provide clear selection recommendations

        ## ANALYSIS APPROACH:

        For each vendor:
        - Review their total score and individual criterion scores
        - Identify their top 3 strengths and top 3 concerns
        - Assess their suitability for the project

        For the comparison:
        - Identify which vendors excel in which areas
        - Note any significant score gaps between vendors
        - Highlight criteria where all vendors performed well or poorly
        - Consider risk factors and value for money

        ## OUTPUT FORMAT:

        Respond with a valid JSON object:

        ```json
        {
          "rfp_title": "RFP title",
          "comparison_date": "YYYY-MM-DD",
          "total_vendors": <number>,
          "vendor_rankings": [
            {
              "rank": 1,
              "vendor_name": "Vendor Name",
              "total_score": 85.5,
              "grade": "B",
              "key_strengths": ["strength 1", "strength 2", "strength 3"],
              "key_concerns": ["concern 1", "concern 2", "concern 3"],
              "recommendation": "Brief recommendation for this vendor"
            }
          ],
          "criterion_comparisons": [
            {
              "criterion_id": "C-1",
              "criterion_name": "Criterion Name",
              "weight": 20.0,
              "best_vendor": "Best Vendor",
              "worst_vendor": "Worst Vendor",
              "score_range": "65-92",
              "insights": "Key insight for this criterion"
            }
          ],
          "winner_summary": "Summary of why the top vendor is recommended",
          "comparison_insights": [
            "Key insight 1",
            "Key insight 2",
            "Key insight 3"
          ],
          "selection_recommendation": "Clear final recommendation with justification",
          "risk_comparison": "Comparative risk assessment across vendors"
        }
        ```

        ## IMPORTANT:
        - Rank ALL vendors by score
        - Compare ALL criteria
        - Be objective and fair
        - Support recommendations with evidence
        - Respond with ONLY valid JSON
        """;

    public ComparisonService(
        IHttpClientFactory httpClientFactory,
        IConfiguration configuration,
        ILogger<ComparisonService> logger)
    {
        _httpClientFactory = httpClientFactory;
        _configuration = configuration;
        _logger = logger;
        _credential = new DefaultAzureCredential();
    }

    public async Task<ComparisonResult> CompareEvaluationsAsync(
        List<EvaluationResult> evaluations,
        string rfpTitle,
        string reasoningEffort = "high",
        Action<string>? progressCallback = null,
        CancellationToken ct = default)
    {
        _logger.LogInformation("Starting comparison of {Count} vendor evaluations", evaluations.Count);
        progressCallback?.Invoke("Preparing vendor comparison...");

        var evaluationsSummary = FormatEvaluationsForPrompt(evaluations);

        var userPrompt = $"""
            Please compare the following vendor evaluations and provide a comprehensive analysis.

            ## RFP TITLE: {rfpTitle}

            ## VENDOR EVALUATIONS:

            {evaluationsSummary}

            ---

            REQUIREMENTS:
            1. Rank all vendors by total score
            2. Compare performance on each criterion
            3. Identify the best and worst performers per criterion
            4. Provide clear selection recommendations
            5. Assess comparative risks

            Respond with ONLY valid JSON matching the schema in your instructions.
            """;

        progressCallback?.Invoke("Analyzing vendor comparisons...");
        var responseText = await CallAzureOpenAIAsync(ComparisonInstructions, userPrompt, reasoningEffort, ct);

        return ParseComparisonResponse(responseText);
    }

    private string FormatEvaluationsForPrompt(List<EvaluationResult> evaluations)
    {
        var parts = new List<string>();

        for (int i = 0; i < evaluations.Count; i++)
        {
            var eval = evaluations[i];
            var sb = new StringBuilder();
            sb.AppendLine($"### Vendor {i + 1}: {eval.SupplierName}");
            sb.AppendLine($"- **Total Score:** {eval.TotalScore:F2}");
            sb.AppendLine($"- **Grade:** {eval.Grade}");
            sb.AppendLine();
            sb.AppendLine("**Criterion Scores:**");

            foreach (var cs in eval.CriterionScores)
            {
                sb.AppendLine($"- {cs.CriterionName}: {cs.RawScore:F1} (weighted: {cs.WeightedScore:F2})");
            }

            if (eval.OverallStrengths.Count > 0)
                sb.AppendLine($"\n**Strengths:** {string.Join(", ", eval.OverallStrengths.Take(5))}");
            if (eval.OverallWeaknesses.Count > 0)
                sb.AppendLine($"\n**Weaknesses:** {string.Join(", ", eval.OverallWeaknesses.Take(5))}");

            parts.Add(sb.ToString());
        }

        return string.Join("\n\n---\n\n", parts);
    }

    private ComparisonResult ParseComparisonResponse(string responseText)
    {
        var text = CleanJsonResponse(responseText);

        try
        {
            using var doc = JsonDocument.Parse(text);
            var root = doc.RootElement;

            var result = new ComparisonResult
            {
                RfpTitle = root.TryGetProperty("rfp_title", out var rt) ? rt.GetString() ?? "" : "",
                ComparisonDate = root.TryGetProperty("comparison_date", out var cd) ? cd.GetString() ?? DateTime.UtcNow.ToString("yyyy-MM-dd") : DateTime.UtcNow.ToString("yyyy-MM-dd"),
                TotalVendors = root.TryGetProperty("total_vendors", out var tv) ? tv.GetInt32() : 0,
                WinnerSummary = root.TryGetProperty("winner_summary", out var ws) ? ws.GetString() ?? "" : "",
                SelectionRecommendation = root.TryGetProperty("selection_recommendation", out var sr) ? sr.GetString() ?? "" : "",
                RiskComparison = root.TryGetProperty("risk_comparison", out var rc) ? rc.GetString() ?? "" : ""
            };

            if (root.TryGetProperty("vendor_rankings", out var rankings))
            {
                foreach (var r in rankings.EnumerateArray())
                {
                    result.VendorRankings.Add(new VendorRanking
                    {
                        Rank = r.TryGetProperty("rank", out var rank) ? rank.GetInt32() : 0,
                        VendorName = r.TryGetProperty("vendor_name", out var vn) ? vn.GetString() ?? "" : "",
                        TotalScore = r.TryGetProperty("total_score", out var ts) ? ts.GetDouble() : 0,
                        Grade = r.TryGetProperty("grade", out var g) ? g.GetString() ?? "" : "",
                        KeyStrengths = r.TryGetProperty("key_strengths", out var ks) ? ks.EnumerateArray().Select(s => s.GetString() ?? "").ToList() : new(),
                        KeyConcerns = r.TryGetProperty("key_concerns", out var kc) ? kc.EnumerateArray().Select(s => s.GetString() ?? "").ToList() : new(),
                        Recommendation = r.TryGetProperty("recommendation", out var rec) ? rec.GetString() ?? "" : ""
                    });
                }
            }

            if (root.TryGetProperty("criterion_comparisons", out var comparisons))
            {
                foreach (var c in comparisons.EnumerateArray())
                {
                    result.CriterionComparisons.Add(new CriterionComparison
                    {
                        CriterionId = c.TryGetProperty("criterion_id", out var cid) ? cid.GetString() ?? "" : "",
                        CriterionName = c.TryGetProperty("criterion_name", out var cn) ? cn.GetString() ?? "" : "",
                        Weight = c.TryGetProperty("weight", out var w) ? w.GetDouble() : 0,
                        BestVendor = c.TryGetProperty("best_vendor", out var bv) ? bv.GetString() ?? "" : "",
                        WorstVendor = c.TryGetProperty("worst_vendor", out var wv) ? wv.GetString() ?? "" : "",
                        ScoreRange = c.TryGetProperty("score_range", out var sr2) ? sr2.GetString() ?? "" : "",
                        Insights = c.TryGetProperty("insights", out var ins) ? ins.GetString() ?? "" : ""
                    });
                }
            }

            if (root.TryGetProperty("comparison_insights", out var insights))
            {
                result.ComparisonInsights = insights.EnumerateArray().Select(s => s.GetString() ?? "").ToList();
            }

            return result;
        }
        catch (JsonException ex)
        {
            _logger.LogError(ex, "Failed to parse comparison JSON");
            return new ComparisonResult
            {
                RfpTitle = "Unknown RFP",
                ComparisonDate = DateTime.UtcNow.ToString("yyyy-MM-dd"),
                WinnerSummary = "Error parsing comparison results",
                SelectionRecommendation = "Unable to provide recommendation due to parsing error"
            };
        }
    }

    public byte[] GenerateCsvReport(ComparisonResult comparison, List<EvaluationResult> evaluations)
    {
        using var ms = new MemoryStream();
        using var writer = new StreamWriter(ms, Encoding.UTF8);

        writer.WriteLine("RFP Comparison Report");
        writer.WriteLine($"RFP Title,{comparison.RfpTitle}");
        writer.WriteLine($"Comparison Date,{comparison.ComparisonDate}");
        writer.WriteLine($"Total Vendors,{comparison.TotalVendors}");
        writer.WriteLine();

        writer.WriteLine("=== VENDOR RANKINGS ===");
        writer.WriteLine("Rank,Vendor Name,Total Score,Grade,Recommendation");
        foreach (var ranking in comparison.VendorRankings)
        {
            writer.WriteLine($"{ranking.Rank},{ranking.VendorName},{ranking.TotalScore:F2},{ranking.Grade},{EscapeCsv(ranking.Recommendation)}");
        }
        writer.WriteLine();

        writer.WriteLine("=== CRITERION COMPARISON ===");
        var header = "Criterion,Weight";
        foreach (var eval in evaluations)
        {
            header += $",{eval.SupplierName}";
        }
        writer.WriteLine(header);

        if (evaluations.Count > 0)
        {
            var allCriteria = evaluations[0].CriterionScores;
            for (int idx = 0; idx < allCriteria.Count; idx++)
            {
                var row = $"{allCriteria[idx].CriterionName},{allCriteria[idx].Weight:F1}%";
                foreach (var eval in evaluations)
                {
                    if (idx < eval.CriterionScores.Count)
                        row += $",{eval.CriterionScores[idx].RawScore:F1}";
                    else
                        row += ",";
                }
                writer.WriteLine(row);
            }

            var totalRow = "TOTAL SCORE,100%";
            foreach (var eval in evaluations)
            {
                totalRow += $",{eval.TotalScore:F2}";
            }
            writer.WriteLine(totalRow);
        }

        writer.WriteLine();
        writer.WriteLine("=== KEY INSIGHTS ===");
        foreach (var insight in comparison.ComparisonInsights)
        {
            writer.WriteLine(EscapeCsv(insight));
        }

        writer.WriteLine();
        writer.WriteLine("=== SELECTION RECOMMENDATION ===");
        writer.WriteLine(EscapeCsv(comparison.SelectionRecommendation));

        writer.Flush();
        return ms.ToArray();
    }

    public byte[] GenerateExcelReport(ComparisonResult comparison, List<EvaluationResult> evaluations)
    {
        using var workbook = new XLWorkbook();

        // Rankings sheet
        var rankingsSheet = workbook.Worksheets.Add("Rankings");
        rankingsSheet.Cell(1, 1).Value = "Rank";
        rankingsSheet.Cell(1, 2).Value = "Vendor";
        rankingsSheet.Cell(1, 3).Value = "Score";
        rankingsSheet.Cell(1, 4).Value = "Grade";
        rankingsSheet.Cell(1, 5).Value = "Recommendation";
        var headerRange = rankingsSheet.Range(1, 1, 1, 5);
        headerRange.Style.Font.Bold = true;

        for (int i = 0; i < comparison.VendorRankings.Count; i++)
        {
            var r = comparison.VendorRankings[i];
            rankingsSheet.Cell(i + 2, 1).Value = r.Rank;
            rankingsSheet.Cell(i + 2, 2).Value = r.VendorName;
            rankingsSheet.Cell(i + 2, 3).Value = r.TotalScore;
            rankingsSheet.Cell(i + 2, 4).Value = r.Grade;
            rankingsSheet.Cell(i + 2, 5).Value = r.Recommendation;
        }
        rankingsSheet.Columns().AdjustToContents();

        // Score comparison sheet
        if (evaluations.Count > 0)
        {
            var scoresSheet = workbook.Worksheets.Add("Score Comparison");
            scoresSheet.Cell(1, 1).Value = "Criterion";
            scoresSheet.Cell(1, 2).Value = "Weight";
            for (int i = 0; i < evaluations.Count; i++)
            {
                scoresSheet.Cell(1, i + 3).Value = evaluations[i].SupplierName;
            }
            var scoreHeader = scoresSheet.Range(1, 1, 1, evaluations.Count + 2);
            scoreHeader.Style.Font.Bold = true;

            var criteria = evaluations[0].CriterionScores;
            for (int idx = 0; idx < criteria.Count; idx++)
            {
                scoresSheet.Cell(idx + 2, 1).Value = criteria[idx].CriterionName;
                scoresSheet.Cell(idx + 2, 2).Value = $"{criteria[idx].Weight:F1}%";
                for (int e = 0; e < evaluations.Count; e++)
                {
                    if (idx < evaluations[e].CriterionScores.Count)
                        scoresSheet.Cell(idx + 2, e + 3).Value = evaluations[e].CriterionScores[idx].RawScore;
                }
            }

            var totalRow = criteria.Count + 2;
            scoresSheet.Cell(totalRow, 1).Value = "TOTAL";
            scoresSheet.Cell(totalRow, 2).Value = "100%";
            for (int e = 0; e < evaluations.Count; e++)
            {
                scoresSheet.Cell(totalRow, e + 3).Value = evaluations[e].TotalScore;
            }
            scoresSheet.Row(totalRow).Style.Font.Bold = true;
            scoresSheet.Columns().AdjustToContents();
        }

        using var ms = new MemoryStream();
        workbook.SaveAs(ms);
        return ms.ToArray();
    }

    private static string EscapeCsv(string value)
    {
        if (string.IsNullOrEmpty(value)) return "";
        if (value.Contains(',') || value.Contains('"') || value.Contains('\n'))
        {
            return $"\"{value.Replace("\"", "\"\"")}\"";
        }
        return value;
    }

    private static string CleanJsonResponse(string text)
    {
        text = text.Trim();
        if (text.StartsWith("```json")) text = text[7..];
        else if (text.StartsWith("```")) text = text[3..];
        if (text.EndsWith("```")) text = text[..^3];
        return text.Trim();
    }

    private async Task<string> CallAzureOpenAIAsync(string systemInstructions, string userPrompt, string reasoningEffort, CancellationToken ct)
    {
        var endpoint = _configuration["AZURE_OPENAI_ENDPOINT"]
            ?? throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT is not configured");
        var deploymentName = _configuration["AZURE_OPENAI_DEPLOYMENT_NAME"]
            ?? throw new InvalidOperationException("AZURE_OPENAI_DEPLOYMENT_NAME is not configured");

        var client = _httpClientFactory.CreateClient();
        var token = await GetTokenAsync(ct);
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

        var url = $"{endpoint.TrimEnd('/')}/openai/deployments/{deploymentName}/chat/completions?api-version=2025-01-01-preview";

        var requestBody = new
        {
            messages = new object[]
            {
                new { role = "system", content = systemInstructions },
                new { role = "user", content = userPrompt }
            },
            reasoning_effort = reasoningEffort
        };

        var json = JsonSerializer.Serialize(requestBody);
        using var httpContent = new StringContent(json, Encoding.UTF8, "application/json");

        var response = await client.PostAsync(url, httpContent, ct);
        response.EnsureSuccessStatusCode();

        var responseJson = await response.Content.ReadAsStringAsync(ct);
        using var doc = JsonDocument.Parse(responseJson);

        var choices = doc.RootElement.GetProperty("choices");
        if (choices.GetArrayLength() > 0)
        {
            return choices[0].GetProperty("message").GetProperty("content").GetString() ?? "";
        }

        return "";
    }

    private async Task<string> GetTokenAsync(CancellationToken ct)
    {
        var tokenResult = await _credential.GetTokenAsync(
            new TokenRequestContext(new[] { "https://cognitiveservices.azure.com/.default" }), ct);
        return tokenResult.Token;
    }
}
