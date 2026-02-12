using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Azure.Core;
using Azure.Identity;
using RfpAnalyzer.Models;

namespace RfpAnalyzer.Services;

public class ScoringService
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IConfiguration _configuration;
    private readonly ILogger<ScoringService> _logger;
    private readonly TokenCredential _credential;

    // The same system instructions from Python's CriteriaExtractionAgent
    private const string CriteriaExtractionInstructions = """
        You are an expert procurement analyst specializing in RFP (Request for Proposal) analysis.

        Your task is to carefully analyze RFP documents and extract comprehensive scoring criteria that will be used to evaluate vendor proposals.

        ## YOUR RESPONSIBILITIES:

        1. **Identify Evaluation Criteria**: Find all evaluation criteria mentioned in the RFP, including:
           - Explicitly stated criteria (often in "Evaluation Criteria" or "Selection Criteria" sections)
           - Implied criteria based on requirements and priorities
           - Industry-standard criteria relevant to the type of work

        2. **Assign Weights**: Distribute 100 total weight points across criteria based on:
           - Explicit weights mentioned in the RFP
           - Emphasis and priority indicated in the document
           - Industry standards for similar projects
           - Balanced evaluation across technical, financial, and qualitative factors

        3. **Provide Evaluation Guidance**: For each criterion, explain:
           - What constitutes excellent performance (90-100 score)
           - What constitutes good performance (70-89 score)
           - What constitutes acceptable performance (50-69 score)
           - What constitutes poor performance (below 50)

        ## WEIGHT DISTRIBUTION GUIDELINES:

        - Technical capabilities: typically 30-50%
        - Experience and track record: typically 15-25%
        - Methodology and approach: typically 15-25%
        - Pricing/value: typically 15-30% (if mentioned)
        - Team qualifications: typically 10-20%

        ## OUTPUT REQUIREMENTS:

        You MUST respond with a valid JSON object matching this exact structure:

        ```json
        {
          "rfp_title": "Extracted RFP title",
          "rfp_summary": "2-3 sentence summary of what the RFP is requesting",
          "total_weight": 100.0,
          "criteria": [
            {
              "criterion_id": "C-1",
              "name": "Criterion Name",
              "description": "Detailed description of what this criterion evaluates",
              "category": "Technical|Financial|Experience|Qualitative",
              "weight": <percentage weight>,
              "max_score": 100,
              "evaluation_guidance": "Detailed guidance on how to score this criterion"
            }
          ],
          "extraction_notes": "Notes about how criteria were identified and weighted"
        }
        ```

        ## IMPORTANT:
        - All weights MUST sum to exactly 100
        - Include at least 4-8 meaningful criteria
        - Be specific in descriptions and guidance
        - Respond with ONLY valid JSON, no additional text
        """;

    private const string ProposalScoringInstructionsTemplate = """
        You are an expert procurement evaluator with extensive experience scoring vendor proposals.

        Your task is to objectively evaluate a vendor proposal against specific scoring criteria extracted from an RFP.

        ## SCORING METHODOLOGY:

        For EACH criterion, you must:

        1. **Find Evidence**: Locate relevant content in the proposal
        2. **Assess Quality**: Compare against the evaluation guidance
        3. **Assign Score**: Score 0-100 based on:
           - 90-100 (Excellent): Exceeds requirements, exceptional quality
           - 70-89 (Good): Fully meets requirements, high quality
           - 50-69 (Acceptable): Meets minimum requirements
           - 30-49 (Below Average): Partially meets requirements
           - 0-29 (Poor): Fails to meet requirements

        4. **Calculate Weighted Score**: weighted_score = (raw_score * weight) / 100

        5. **Document Everything**: Provide evidence, justification, strengths, and gaps

        ## EVALUATION CRITERIA TO USE:

        {0}

        ## GRADE ASSIGNMENT:

        Based on total weighted score:
        - A: 90-100
        - B: 80-89
        - C: 70-79
        - D: 60-69
        - F: Below 60

        ## OUTPUT FORMAT:

        You MUST respond with a valid JSON object:

        ```json
        {{
          "rfp_title": "RFP title",
          "supplier_name": "Extracted vendor name",
          "supplier_site": "Vendor location",
          "response_id": "Generate ID like RESP-2025-XXXX",
          "evaluation_date": "YYYY-MM-DD",
          "total_score": <sum of all weighted scores>,
          "score_percentage": <total_score as percentage>,
          "grade": "A/B/C/D/F",
          "recommendation": "Clear recommendation statement",
          "criterion_scores": [
            {{
              "criterion_id": "C-1",
              "criterion_name": "Criterion Name",
              "weight": <weight>,
              "raw_score": <0-100>,
              "weighted_score": <calculated>,
              "evidence": "Specific evidence from proposal",
              "justification": "Detailed scoring justification",
              "strengths": ["strength1", "strength2"],
              "gaps": ["gap1", "gap2"]
            }}
          ],
          "executive_summary": "2-3 paragraph executive summary",
          "overall_strengths": ["key strength 1", "key strength 2"],
          "overall_weaknesses": ["key weakness 1", "key weakness 2"],
          "recommendations": ["recommendation 1", "recommendation 2"],
          "risk_assessment": "Assessment of risks with this vendor"
        }}
        ```

        ## IMPORTANT:
        - Score EVERY criterion from the provided list
        - Provide specific evidence from the proposal
        - Be objective and fair
        - Respond with ONLY valid JSON
        """;

    public ScoringService(
        IHttpClientFactory httpClientFactory,
        IConfiguration configuration,
        ILogger<ScoringService> logger)
    {
        _httpClientFactory = httpClientFactory;
        _configuration = configuration;
        _logger = logger;
        _credential = new DefaultAzureCredential();
    }

    public async Task<EvaluationResult> EvaluateAsync(
        string rfpContent,
        string proposalContent,
        string reasoningEffort = "high",
        Action<string>? progressCallback = null,
        CancellationToken ct = default)
    {
        var totalStart = DateTime.UtcNow;
        _logger.LogInformation("V2 Multi-Agent evaluation started (effort: {Effort})", reasoningEffort);

        // Phase 1: Extract criteria
        progressCallback?.Invoke("Phase 1: Extracting scoring criteria from RFP...");
        var phase1Start = DateTime.UtcNow;
        var criteria = await ExtractCriteriaAsync(rfpContent, reasoningEffort, progressCallback, ct);
        var phase1Duration = (DateTime.UtcNow - phase1Start).TotalSeconds;
        _logger.LogInformation("Phase 1 completed in {Duration:F2}s - Extracted {Count} criteria",
            phase1Duration, criteria.Criteria.Count);

        // Phase 2: Score proposal
        progressCallback?.Invoke("Phase 2: Scoring proposal against extracted criteria...");
        var phase2Start = DateTime.UtcNow;
        var evaluation = await ScoreProposalAsync(criteria, proposalContent, reasoningEffort, progressCallback, ct);
        var phase2Duration = (DateTime.UtcNow - phase2Start).TotalSeconds;
        _logger.LogInformation("Phase 2 completed in {Duration:F2}s - Total score: {Score:F2}",
            phase2Duration, evaluation.TotalScore);

        var totalDuration = (DateTime.UtcNow - totalStart).TotalSeconds;

        // Build result
        var result = new EvaluationResult
        {
            RfpTitle = evaluation.RfpTitle,
            SupplierName = evaluation.SupplierName,
            SupplierSite = evaluation.SupplierSite,
            ResponseId = evaluation.ResponseId,
            TotalScore = evaluation.TotalScore,
            ScorePercentage = evaluation.ScorePercentage,
            Grade = evaluation.Grade,
            Recommendation = evaluation.Recommendation,
            ExtractedCriteria = criteria,
            CriterionScores = evaluation.CriterionScores,
            ExecutiveSummary = evaluation.ExecutiveSummary,
            OverallStrengths = evaluation.OverallStrengths,
            OverallWeaknesses = evaluation.OverallWeaknesses,
            Recommendations = evaluation.Recommendations,
            RiskAssessment = evaluation.RiskAssessment,
            Metadata = new EvaluationMetadata
            {
                Version = "2.0",
                EvaluationType = "multi-agent",
                EvaluationTimestamp = DateTime.UtcNow.ToString("o"),
                TotalDurationSeconds = Math.Round(totalDuration, 2),
                Phase1CriteriaExtractionSeconds = Math.Round(phase1Duration, 2),
                Phase2ProposalScoringSeconds = Math.Round(phase2Duration, 2),
                CriteriaCount = criteria.Criteria.Count,
                ModelDeployment = _configuration["AZURE_OPENAI_DEPLOYMENT_NAME"] ?? "",
                ReasoningEffort = reasoningEffort
            }
        };

        _logger.LogInformation("V2 Multi-Agent evaluation completed in {Duration:F2}s", totalDuration);
        return result;
    }

    private async Task<ExtractedCriteria> ExtractCriteriaAsync(
        string rfpContent, string reasoningEffort, Action<string>? progressCallback, CancellationToken ct)
    {
        progressCallback?.Invoke("Analyzing RFP structure and requirements...");

        var userPrompt = $"""
            Please analyze the following RFP document and extract comprehensive scoring criteria.

            ## RFP DOCUMENT:

            {rfpContent}

            ---

            REQUIREMENTS:
            1. Identify all evaluation criteria (explicit and implied)
            2. Assign weights that sum to exactly 100
            3. Provide detailed evaluation guidance for each criterion
            4. Include the RFP title and a brief summary

            Respond with ONLY valid JSON matching the schema in your instructions.
            """;

        progressCallback?.Invoke("Extracting and analyzing criteria...");
        var responseText = await CallAzureOpenAIAsync(CriteriaExtractionInstructions, userPrompt, reasoningEffort, ct);

        return ParseCriteriaResponse(responseText);
    }

    private async Task<ProposalEvaluation> ScoreProposalAsync(
        ExtractedCriteria criteria, string proposalContent, string reasoningEffort,
        Action<string>? progressCallback, CancellationToken ct)
    {
        progressCallback?.Invoke("Preparing scoring framework...");

        var criteriaJson = JsonSerializer.Serialize(criteria.Criteria.Select(c => new
        {
            criterion_id = c.CriterionId,
            name = c.Name,
            description = c.Description,
            category = c.Category,
            weight = c.Weight,
            max_score = c.MaxScore,
            evaluation_guidance = c.EvaluationGuidance
        }), new JsonSerializerOptions { WriteIndented = true });

        var systemInstructions = string.Format(ProposalScoringInstructionsTemplate, criteriaJson);

        var userPrompt = $"""
            Please evaluate the following vendor proposal against the scoring criteria.

            ## RFP CONTEXT:
            - Title: {criteria.RfpTitle}
            - Summary: {criteria.RfpSummary}

            ## VENDOR PROPOSAL:

            {proposalContent}

            ---

            REQUIREMENTS:
            1. Score each criterion from 0-100
            2. Calculate weighted scores
            3. Provide evidence and justification for each score
            4. Summarize strengths, weaknesses, and recommendations
            5. Assign an overall grade

            Respond with ONLY valid JSON matching the schema in your instructions.
            """;

        progressCallback?.Invoke("Scoring proposal against criteria...");
        var responseText = await CallAzureOpenAIAsync(systemInstructions, userPrompt, reasoningEffort, ct);

        return ParseScoringResponse(responseText, criteria);
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

        // Use the responses API endpoint (compatible with agent-framework)
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

    private ExtractedCriteria ParseCriteriaResponse(string responseText)
    {
        var text = CleanJsonResponse(responseText);

        try
        {
            using var doc = JsonDocument.Parse(text);
            var root = doc.RootElement;

            var criteria = new ExtractedCriteria
            {
                RfpTitle = root.GetProperty("rfp_title").GetString() ?? "Unknown RFP",
                RfpSummary = root.GetProperty("rfp_summary").GetString() ?? "",
                ExtractionNotes = root.TryGetProperty("extraction_notes", out var notes) ? notes.GetString() ?? "" : ""
            };

            if (root.TryGetProperty("criteria", out var criteriaArray))
            {
                foreach (var c in criteriaArray.EnumerateArray())
                {
                    criteria.Criteria.Add(new ScoringCriterion
                    {
                        CriterionId = c.GetProperty("criterion_id").GetString() ?? "",
                        Name = c.GetProperty("name").GetString() ?? "",
                        Description = c.TryGetProperty("description", out var desc) ? desc.GetString() ?? "" : "",
                        Category = c.TryGetProperty("category", out var cat) ? cat.GetString() ?? "" : "",
                        Weight = c.GetProperty("weight").GetDouble(),
                        MaxScore = c.TryGetProperty("max_score", out var ms) ? ms.GetInt32() : 100,
                        EvaluationGuidance = c.TryGetProperty("evaluation_guidance", out var eg) ? eg.GetString() ?? "" : ""
                    });
                }
            }

            // Normalize weights
            var totalWeight = criteria.Criteria.Sum(c => c.Weight);
            if (criteria.Criteria.Count > 0 && Math.Abs(totalWeight - 100) > 0.1)
            {
                _logger.LogWarning("Normalizing weights from {Total} to 100", totalWeight);
                foreach (var c in criteria.Criteria)
                {
                    c.Weight = c.Weight / totalWeight * 100;
                }
            }
            criteria.TotalWeight = 100.0;

            return criteria;
        }
        catch (JsonException ex)
        {
            _logger.LogError(ex, "Failed to parse criteria JSON");
            return new ExtractedCriteria
            {
                RfpTitle = "Unknown RFP",
                RfpSummary = "Failed to extract RFP summary",
                ExtractionNotes = $"Error parsing response: {ex.Message}"
            };
        }
    }

    private ProposalEvaluation ParseScoringResponse(string responseText, ExtractedCriteria criteria)
    {
        var text = CleanJsonResponse(responseText);

        try
        {
            using var doc = JsonDocument.Parse(text);
            var root = doc.RootElement;

            var evaluation = new ProposalEvaluation
            {
                RfpTitle = root.TryGetProperty("rfp_title", out var rt) ? rt.GetString() ?? "" : criteria.RfpTitle,
                SupplierName = root.TryGetProperty("supplier_name", out var sn) ? sn.GetString() ?? "Unknown Vendor" : "Unknown Vendor",
                SupplierSite = root.TryGetProperty("supplier_site", out var ss) ? ss.GetString() ?? "" : "",
                ResponseId = root.TryGetProperty("response_id", out var ri) ? ri.GetString() ?? "" : "",
                EvaluationDate = root.TryGetProperty("evaluation_date", out var ed) ? ed.GetString() ?? DateTime.UtcNow.ToString("yyyy-MM-dd") : DateTime.UtcNow.ToString("yyyy-MM-dd"),
                Recommendation = root.TryGetProperty("recommendation", out var rec) ? rec.GetString() ?? "" : "",
                ExecutiveSummary = root.TryGetProperty("executive_summary", out var es) ? es.GetString() ?? "" : "",
                RiskAssessment = root.TryGetProperty("risk_assessment", out var ra) ? ra.GetString() ?? "" : ""
            };

            // Parse criterion scores
            if (root.TryGetProperty("criterion_scores", out var scoresArray))
            {
                foreach (var cs in scoresArray.EnumerateArray())
                {
                    evaluation.CriterionScores.Add(new CriterionScore
                    {
                        CriterionId = cs.TryGetProperty("criterion_id", out var cid) ? cid.GetString() ?? "" : "",
                        CriterionName = cs.TryGetProperty("criterion_name", out var cn) ? cn.GetString() ?? "" : "",
                        Weight = cs.TryGetProperty("weight", out var w) ? w.GetDouble() : 0,
                        RawScore = cs.TryGetProperty("raw_score", out var rs) ? rs.GetDouble() : 0,
                        WeightedScore = cs.TryGetProperty("weighted_score", out var ws) ? ws.GetDouble() : 0,
                        Evidence = cs.TryGetProperty("evidence", out var ev) ? ev.GetString() ?? "" : "",
                        Justification = cs.TryGetProperty("justification", out var j) ? j.GetString() ?? "" : "",
                        Strengths = cs.TryGetProperty("strengths", out var str) ? str.EnumerateArray().Select(s => s.GetString() ?? "").ToList() : new(),
                        Gaps = cs.TryGetProperty("gaps", out var g) ? g.EnumerateArray().Select(s => s.GetString() ?? "").ToList() : new()
                    });
                }
            }

            // Parse string arrays
            evaluation.OverallStrengths = ParseStringArray(root, "overall_strengths");
            evaluation.OverallWeaknesses = ParseStringArray(root, "overall_weaknesses");
            evaluation.Recommendations = ParseStringArray(root, "recommendations");

            // Recalculate total score for accuracy
            var totalScore = evaluation.CriterionScores.Sum(cs => cs.WeightedScore);
            evaluation.TotalScore = Math.Round(totalScore, 2);
            evaluation.ScorePercentage = Math.Round(totalScore, 2);

            // Determine grade
            evaluation.Grade = totalScore switch
            {
                >= 90 => "A",
                >= 80 => "B",
                >= 70 => "C",
                >= 60 => "D",
                _ => "F"
            };

            return evaluation;
        }
        catch (JsonException ex)
        {
            _logger.LogError(ex, "Failed to parse scoring JSON");
            return new ProposalEvaluation
            {
                RfpTitle = criteria.RfpTitle,
                SupplierName = "Unknown Vendor",
                EvaluationDate = DateTime.UtcNow.ToString("yyyy-MM-dd"),
                Grade = "F",
                Recommendation = "Unable to complete evaluation due to parsing error"
            };
        }
    }

    private static string CleanJsonResponse(string text)
    {
        text = text.Trim();
        if (text.StartsWith("```json")) text = text[7..];
        else if (text.StartsWith("```")) text = text[3..];
        if (text.EndsWith("```")) text = text[..^3];
        return text.Trim();
    }

    private static List<string> ParseStringArray(JsonElement root, string propertyName)
    {
        if (root.TryGetProperty(propertyName, out var array))
        {
            return array.EnumerateArray().Select(s => s.GetString() ?? "").ToList();
        }
        return new();
    }

    private async Task<string> GetTokenAsync(CancellationToken ct)
    {
        var tokenResult = await _credential.GetTokenAsync(
            new TokenRequestContext(new[] { "https://cognitiveservices.azure.com/.default" }), ct);
        return tokenResult.Token;
    }
}
