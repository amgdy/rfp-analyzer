"""CSS styles and constants for the RFP Analyzer UI."""

# CSS for the session ID top bar shown on all pages
SESSION_HEADER_CSS = """
<style>
.session-header {
    background: #F3F4F6;
    border-bottom: 1px solid #E5E7EB;
    padding: 6px 16px;
    border-radius: 6px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8rem;
    color: #6B7280;
}
.session-header code {
    background: #E5E7EB;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.75rem;
    color: #374151;
}
</style>
"""

# CSS for the full-page loading overlay that grays out content
LOADING_OVERLAY_CSS = """
<style>
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
}
.loading-box {
    background: white;
    border-radius: 12px;
    padding: 32px 48px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    text-align: center;
    max-width: 400px;
}
.loading-box h3 {
    margin: 16px 0 8px 0;
    color: #1F2937;
    font-size: 1.25rem;
}
.loading-box p {
    color: #6B7280;
    font-size: 0.9rem;
    margin: 0;
}
.loading-spinner {
    display: inline-block;
    width: 40px;
    height: 40px;
    border: 4px solid #E5E7EB;
    border-radius: 50%;
    border-top-color: #4F46E5;
    animation: loading-spin 0.8s linear infinite;
}
@keyframes loading-spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
"""

# CSS for styled export download links
EXPORT_LINK_CSS = """
<style>
.export-link-card {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 8px;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.export-link-card:hover {
    border-color: #6366F1;
    box-shadow: 0 2px 8px rgba(99,102,241,0.15);
}
.export-link-card a {
    text-decoration: none;
    color: #4F46E5;
    font-weight: 600;
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    gap: 6px;
}
.export-link-card a:hover {
    color: #4338CA;
    text-decoration: underline;
}
.export-link-card .link-desc {
    color: #6B7280;
    font-size: 0.8rem;
    margin-top: 4px;
}
.export-link-card .link-meta {
    color: #9CA3AF;
    font-size: 0.75rem;
    margin-top: 2px;
}
</style>
"""

STEP_ANIMATION_CSS = """
<style>
@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.4; }
    100% { opacity: 1; }
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.step-processing {
    animation: pulse 1.5s ease-in-out infinite;
    background: linear-gradient(90deg, #1f77b4, #2ca02c, #1f77b4);
    background-size: 200% 100%;
    animation: pulse 1.5s ease-in-out infinite, gradient 2s ease infinite;
    padding: 10px;
    border-radius: 8px;
    margin: 5px 0;
}

@keyframes gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.spinner {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s ease-in-out infinite;
    margin-right: 10px;
}

.processing-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    color: white;
    margin: 10px 0;
}

.duration-badge {
    background: rgba(0,0,0,0.2);
    padding: 4px 12px;
    border-radius: 15px;
    font-size: 14px;
    margin-left: 10px;
}
</style>
"""
