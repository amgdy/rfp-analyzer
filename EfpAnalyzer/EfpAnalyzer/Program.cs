using EfpAnalyzer.Components;
using EfpAnalyzer.Models;
using EfpAnalyzer.Services;
using MudBlazor.Services;

var builder = WebApplication.CreateBuilder(args);

// Add configuration from environment variables
builder.Configuration.AddEnvironmentVariables();

// Add services to the container
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

builder.Services.AddMudServices();
builder.Services.AddHttpClient();

// Register application services
builder.Services.AddSingleton<AppState>();
builder.Services.AddScoped<DocumentProcessorService>();
builder.Services.AddScoped<ScoringService>();
builder.Services.AddScoped<ComparisonService>();

var app = builder.Build();

// Configure the HTTP request pipeline
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
    app.UseHttpsRedirection();
}

app.UseAntiforgery();
app.UseStaticFiles();
app.MapStaticAssets();
app.MapGet("/health", () => Results.Ok("Healthy"));
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();
