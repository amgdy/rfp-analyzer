# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability within RFP Analyzer, please follow these steps:

### Do NOT

- Open a public GitHub issue for security vulnerabilities
- Disclose the vulnerability publicly before it has been addressed

### Do

1. **Email us directly** at [security@your-org.com] with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

2. **Allow time for response** - We will acknowledge receipt within 48 hours and provide an estimated timeline for a fix.

3. **Coordinate disclosure** - Work with us to coordinate the public disclosure after a fix is available.

## Security Best Practices

When deploying RFP Analyzer, follow these security best practices:

### Authentication & Authorization

1. **Use Managed Identity** (Recommended)
   - Azure Container Apps is configured with User-Assigned Managed Identity
   - No credentials stored in code or environment variables
   - Automatic credential rotation

2. **Service Principal** (Alternative)
   - If using service principal, store credentials in Azure Key Vault
   - Rotate secrets regularly (at least every 90 days)
   - Use least-privilege principle for role assignments

3. **Azure RBAC Roles**
   The application requires these minimum roles:
   - `Cognitive Services User` - For AI service access
   - `Azure AI Developer` - For AI Foundry operations
   - `AcrPull` - For container image pulls

### Network Security

1. **Private Endpoints** (Production)
   - Configure private endpoints for Azure AI services
   - Use VNet integration for Container Apps
   - Restrict public access to essential endpoints only

2. **Ingress Control**
   - Enable HTTPS only (HTTP redirects to HTTPS)
   - Configure IP restrictions if needed
   - Use Azure Front Door or Application Gateway for WAF protection

### Data Protection

1. **In Transit**
   - All communication uses TLS 1.2+
   - Azure services enforce encrypted connections

2. **At Rest**
   - Uploaded documents are processed in memory
   - No persistent storage of sensitive data
   - Azure AI services encrypt data at rest

3. **Data Handling**
   - Documents are not retained after processing
   - Clear session state after use
   - No logging of document contents

### Application Security

1. **Dependencies**
   - Regularly update dependencies (`uv sync --upgrade`)
   - Monitor for CVEs in dependencies
   - Use `uv audit` to check for vulnerabilities

2. **Environment Variables**
   - Never commit `.env` files
   - Use Azure Key Vault for production secrets
   - Rotate API keys if exposed

3. **Logging**
   - Sensitive data is not logged
   - Enable Application Insights for security monitoring
   - Configure alerts for suspicious activity

### Container Security

1. **Image Security**
   - Base image: `python:3.13-slim` (minimal attack surface)
   - Regular base image updates
   - No root user in container

2. **Registry Security**
   - Private Azure Container Registry
   - Managed identity for image pulls
   - Enable vulnerability scanning

### Compliance Considerations

When processing RFP documents, consider:

1. **Data Classification**
   - RFPs may contain confidential business information
   - Vendor proposals may have proprietary content
   - Implement appropriate access controls

2. **Data Residency**
   - Deploy Azure resources in appropriate regions
   - Understand Azure AI data processing locations
   - Configure data residency as required

3. **Audit Logging**
   - Enable Azure Activity Log
   - Configure Log Analytics for retention
   - Implement access auditing

## Security Checklist for Deployment

### Pre-Deployment

- [ ] Review and update all dependencies
- [ ] Scan container image for vulnerabilities
- [ ] Configure managed identity (not service principal with secrets)
- [ ] Review RBAC role assignments (least privilege)
- [ ] Configure network security (VNet, private endpoints if required)

### Deployment

- [ ] Deploy to appropriate Azure region
- [ ] Enable HTTPS only
- [ ] Configure Application Insights
- [ ] Verify no secrets in logs
- [ ] Test authentication flows

### Post-Deployment

- [ ] Enable Azure Security Center recommendations
- [ ] Configure security alerts
- [ ] Document incident response procedures
- [ ] Schedule regular security reviews
- [ ] Plan for dependency updates

## Security Updates

Security updates will be released as patch versions. Subscribe to repository releases to be notified of security patches.

## Contact

For security concerns, contact: [security@your-org.com]
