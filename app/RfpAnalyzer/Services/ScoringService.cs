using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using OpenAI.Chat;
using RfpAnalyzer.Models;
using System.Text.Json;

namespace RfpAnalyzer.Services;

/// <summary>
/// Multi-agent scoring service using Microsoft Agent Framework.
/// Uses two specialized agents:
///   1. CriteriaExtractionAgent - Analyzes RFPs and extracts scoring criteria
///   2. ProposalScoringAgent - Scores vendor proposals against extracted criteria
/// </summary>
public class ScoringService
{
    private readonly IConfiguration _configuration;
    private readonly ILogger<ScoringService> _logger;

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
        IConfiguration configuration,
        ILogger<ScoringService> logger)
    {
        _configuration = configuration;
        _logger = logger;
    }

    /// <summary>
    /// Creates the Azure OpenAI-backed CriteriaExtractionAgent using Microsoft Agent Framework.
    /// This agent is responsible for analyzing RFP documents and extracting scoring criteria.
    /// </summary>
    internal AIAgent CreateCriteriaExtractionAgent()
    {
        var chatClient = CreateAzureOpenAIChatClient();
        return chatClient.AsAIAgent(
            instructions: CriteriaExtractionInstructions,
            name: "CriteriaExtractionAgent",
            description: "Analyzes RFP documents and extracts comprehensive scoring criteria with weights");
    }

    /// <summary>
    /// Creates the Azure OpenAI-backed ProposalScoringAgent using Microsoft Agent Framework.
    /// This agent scores vendor proposals against the extracted criteria.
    /// </summary>
    internal AIAgent CreateProposalScoringAgent(string criteriaJson)
    {
        var systemInstructions = string.Format(ProposalScoringInstructionsTemplate, criteriaJson);
        var chatClient = CreateAzureOpenAIChatClient();
        return chatClient.AsAIAgent(
            instructions: systemInstructions,
            name: "ProposalScoringAgent",
            description: "Scores a vendor proposal against extracted RFP criteria and provides detailed evaluation");
    }

    /// <summary>
    /// Creates the Orchestrator Agent that coordinates between CriteriaExtractionAgent and ProposalScoringAgent.
    /// Uses the Microsoft Agent Framework multi-agent pattern (agent-as-function-tool).
    /// The orchestrator exposes the specialized agents as function tools via AsAIFunction()
    /// and delegates work to them as appropriate.
    /// </summary>
    internal AIAgent CreateOrchestratorAgent(AIAgent criteriaAgent, AIAgent scoringAgent)
    {
        var chatClient = CreateAzureOpenAIChatClient();

        // Expose each specialist agent as a callable function tool for the orchestrator
        var criteriaFunction = criteriaAgent.AsAIFunction();
        var scoringFunction = scoringAgent.AsAIFunction();

        return chatClient.AsAIAgent(
            instructions: """
                You are the RFP Evaluation Orchestrator. You coordinate between two specialist agents:

                1. **CriteriaExtractionAgent** - Call this first to extract scoring criteria from the RFP document.
                   Pass the full RFP content. It returns JSON with criteria, weights, and evaluation guidance.

                2. **ProposalScoringAgent** - Call this second to score a vendor proposal against criteria.
                   Pass the vendor proposal content along with the RFP context. It returns JSON with scores and analysis.

                When given an evaluation request, you MUST:
                1. First invoke CriteriaExtractionAgent with the RFP content
                2. Then invoke ProposalScoringAgent with the proposal content and RFP context
                3. Return the ProposalScoringAgent's complete JSON response exactly as received

                Do NOT modify, summarize, or reformat the agent responses.
                Return the final scoring agent's JSON output directly.
                """,
            name: "RfpEvaluationOrchestrator",
            description: "Orchestrates the multi-agent RFP evaluation workflow",
            tools: [criteriaFunction, scoringFunction]);
    }

    public async Task<EvaluationResult> EvaluateAsync(
        string rfpContent,
        string proposalContent,
        string reasoningEffort = "high",
        Action<string>? progressCallback = null,
        CancellationToken ct = default)
    {
        var totalStart = DateTime.UtcNow;
        _logger.LogInformation("Multi-Agent evaluation started using Microsoft Agent Framework (effort: {Effort})", reasoningEffort);

        // Phase 1: CriteriaExtractionAgent extracts criteria from RFP
        progressCallback?.Invoke("Phase 1: CriteriaExtractionAgent analyzing RFP...");
        var phase1Start = DateTime.UtcNow;
        var criteria = await ExtractCriteriaWithAgentAsync(rfpContent, reasoningEffort, progressCallback, ct);
        var phase1Duration = (DateTime.UtcNow - phase1Start).TotalSeconds;
        _logger.LogInformation("Phase 1 completed in {Duration:F2}s - Extracted {Count} criteria",
            phase1Duration, criteria.Criteria.Count);

        // Phase 2: ProposalScoringAgent scores proposal against extracted criteria
        progressCallback?.Invoke("Phase 2: ProposalScoringAgent scoring proposal...");
        var phase2Start = DateTime.UtcNow;
        var evaluation = await ScoreProposalWithAgentAsync(criteria, proposalContent, reasoningEffort, progressCallback, ct);
        var phase2Duration = (DateTime.UtcNow - phase2Start).TotalSeconds;
        _logger.LogInformation("Phase 2 completed in {Duration:F2}s - Total score: {Score:F2}",
            phase2Duration, evaluation.TotalScore);

        var totalDuration = (DateTime.UtcNow - totalStart).TotalSeconds;

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
                Version = "3.0",
                EvaluationType = "microsoft-agent-framework",
                EvaluationTimestamp = DateTime.UtcNow.ToString("o"),
                TotalDurationSeconds = Math.Round(totalDuration, 2),
                Phase1CriteriaExtractionSeconds = Math.Round(phase1Duration, 2),
                Phase2ProposalScoringSeconds = Math.Round(phase2Duration, 2),
                CriteriaCount = criteria.Criteria.Count,
                ModelDeployment = _configuration["AZURE_OPENAI_DEPLOYMENT_NAME"] ?? string.Empty,
                ReasoningEffort = reasoningEffort
            }
        };

        _logger.LogInformation("Multi-Agent evaluation completed in {Duration:F2}s", totalDuration);
        return result;
    }

    private async Task<ExtractedCriteria> ExtractCriteriaWithAgentAsync(
        string rfpContent, string reasoningEffort, Action<string>? progressCallback, CancellationToken ct)
    {
        progressCallback?.Invoke("CriteriaExtractionAgent analyzing RFP structure...");

        var agent = CreateCriteriaExtractionAgent();
        var session = await agent.CreateSessionAsync(ct);

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

        progressCallback?.Invoke("CriteriaExtractionAgent extracting criteria...");

        var runOptions = new AgentRunOptions
        {
            AdditionalProperties = new AdditionalPropertiesDictionary
            {
                ["reasoning_effort"] = reasoningEffort
            }
        };

        var response = await agent.RunAsync(userPrompt, session, runOptions, ct);
        var responseText = response.Text ?? "";

        return ParseCriteriaResponse(responseText);
    }

    private async Task<ProposalEvaluation> ScoreProposalWithAgentAsync(
        ExtractedCriteria criteria, string proposalContent, string reasoningEffort,
        Action<string>? progressCallback, CancellationToken ct)
    {
        progressCallback?.Invoke("ProposalScoringAgent preparing scoring framework...");

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

        var agent = CreateProposalScoringAgent(criteriaJson);
        var session = await agent.CreateSessionAsync(ct);

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

        progressCallback?.Invoke("ProposalScoringAgent scoring proposal...");

        var runOptions = new AgentRunOptions
        {
            AdditionalProperties = new AdditionalPropertiesDictionary
            {
                ["reasoning_effort"] = reasoningEffort
            }
        };

        var response = await agent.RunAsync(userPrompt, session, runOptions, ct);
        var responseText = response.Text ?? "";

        return ParseScoringResponse(responseText, criteria);
    }

    private OpenAI.Chat.ChatClient CreateAzureOpenAIChatClient()
    {
        var endpoint = _configuration["AZURE_OPENAI_ENDPOINT"];
        if (string.IsNullOrWhiteSpace(endpoint))
            throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT is not configured. Set it in appsettings.json, appsettings.Development.json, or as an environment variable.");
        var deploymentName = _configuration["AZURE_OPENAI_DEPLOYMENT_NAME"];
        if (string.IsNullOrWhiteSpace(deploymentName))
            throw new InvalidOperationException("AZURE_OPENAI_DEPLOYMENT_NAME is not configured. Set it in appsettings.json, appsettings.Development.json, or as an environment variable.");

        // AzureOpenAIClient expects the base endpoint without path segments like /openai/
        var endpointUri = new Uri(endpoint);
        var baseEndpoint = new Uri($"{endpointUri.Scheme}://{endpointUri.Host}/");

        var client = new AzureOpenAIClient(
            baseEndpoint,
            new DefaultAzureCredential());

        return client.GetChatClient(deploymentName);
    }

    internal ExtractedCriteria ParseCriteriaResponse(string responseText)
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

    internal ProposalEvaluation ParseScoringResponse(string responseText, ExtractedCriteria criteria)
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

            evaluation.OverallStrengths = ParseStringArray(root, "overall_strengths");
            evaluation.OverallWeaknesses = ParseStringArray(root, "overall_weaknesses");
            evaluation.Recommendations = ParseStringArray(root, "recommendations");

            var totalScore = evaluation.CriterionScores.Sum(cs => cs.WeightedScore);
            evaluation.TotalScore = Math.Round(totalScore, 2);
            evaluation.ScorePercentage = Math.Round(totalScore, 2);

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

    internal static string CleanJsonResponse(string text)
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
}
