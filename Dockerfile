# =============================================================================
# EFP Analyzer - Dockerfile (.NET 10 Blazor)
# =============================================================================
# Multi-stage build for optimized image size

# -----------------------------------------------------------------------------
# Stage 1: Build stage
# -----------------------------------------------------------------------------
FROM mcr.microsoft.com/dotnet/sdk:10.0-preview AS build

WORKDIR /src

# Copy solution and project files first for better caching
COPY EfpAnalyzer/EfpAnalyzer.slnx ./EfpAnalyzer/
COPY EfpAnalyzer/global.json ./EfpAnalyzer/
COPY EfpAnalyzer/EfpAnalyzer/EfpAnalyzer.csproj ./EfpAnalyzer/EfpAnalyzer/

# Restore dependencies
RUN dotnet restore EfpAnalyzer/EfpAnalyzer/EfpAnalyzer.csproj

# Copy all source code
COPY EfpAnalyzer/ ./EfpAnalyzer/

# Build and publish
RUN dotnet publish EfpAnalyzer/EfpAnalyzer/EfpAnalyzer.csproj -c Release -o /app/publish --no-restore

# -----------------------------------------------------------------------------
# Stage 2: Runtime stage
# -----------------------------------------------------------------------------
FROM mcr.microsoft.com/dotnet/aspnet:10.0-preview AS runtime

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy published output from build stage
COPY --from=build /app/publish .

# Set environment variables
ENV ASPNETCORE_URLS=http://+:8501
ENV ASPNETCORE_ENVIRONMENT=Production
ENV DOTNET_RUNNING_IN_CONTAINER=true

# Switch to non-root user
USER appuser

# Expose port (matching original Streamlit port for IaC compatibility)
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/health || exit 1

# Run the application
ENTRYPOINT ["dotnet", "EfpAnalyzer.dll"]
