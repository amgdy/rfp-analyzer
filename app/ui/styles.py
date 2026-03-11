"""CSS styles and constants for the RFP Analyzer UI."""

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
