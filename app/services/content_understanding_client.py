"""
Azure Content Understanding Client.

This is a simplified client for Azure Content Understanding based on the official
Azure Samples: https://github.com/Azure-Samples/azure-ai-content-understanding-python
"""

import logging
import requests
import time
from typing import Any, Dict, Optional
from pathlib import Path


POLL_TIMEOUT_SECONDS = 180


class AzureContentUnderstandingClient:
    """
    Client for Azure Content Understanding API.
    
    Uses the prebuilt-documentSearch analyzer to extract content from documents
    and return as markdown.
    """
    
    PREBUILT_DOCUMENT_ANALYZER_ID: str = "prebuilt-documentSearch"
    
    def __init__(
        self,
        endpoint: str,
        api_version: str = "2025-11-01",
        subscription_key: str = None,
        token_provider: callable = None,
        x_ms_useragent: str = "rfp-analyzer",
    ):
        """
        Initialize the Azure Content Understanding client.
        
        Args:
            endpoint: The Azure AI Services endpoint URL
            api_version: The API version to use (default: 2025-11-01)
            subscription_key: The subscription key for authentication
            token_provider: A callable that returns an access token
            x_ms_useragent: User agent string for tracking
        """
        if not subscription_key and not token_provider:
            raise ValueError(
                "Either subscription key or token provider must be provided."
            )
        if not api_version:
            raise ValueError("API version must be provided.")
        if not endpoint:
            raise ValueError("Endpoint must be provided.")

        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version
        self._logger = logging.getLogger(__name__)

        token = token_provider() if token_provider else None
        self._headers = self._get_headers(subscription_key, token, x_ms_useragent)

    def _get_headers(
        self, subscription_key: str, api_token: str, x_ms_useragent: str
    ) -> Dict[str, str]:
        """Build request headers."""
        headers = {"x-ms-useragent": x_ms_useragent}
        if subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = subscription_key
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        return headers

    def _get_analyze_binary_url(self, analyzer_id: str) -> str:
        """Get the URL for binary analysis."""
        return f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyzeBinary?api-version={self._api_version}"

    def _get_analyze_url(self, analyzer_id: str) -> str:
        """Get the URL for URL-based analysis."""
        return f"{self._endpoint}/contentunderstanding/analyzers/{analyzer_id}:analyze?api-version={self._api_version}"

    def _raise_for_status_with_detail(self, response: requests.Response) -> None:
        """Raise HTTPError with detailed error information."""
        if response.ok:
            return
        
        try:
            error_detail = ""
            try:
                error_json = response.json()
                if "error" in error_json:
                    error_info = error_json["error"]
                    error_code = error_info.get("code", "Unknown")
                    error_message = error_info.get("message", "No message provided")
                    error_detail = f"\n  Error Code: {error_code}\n  Error Message: {error_message}"
            except Exception:
                error_detail = f"\n  Response: {response.text[:500]}"
            
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise requests.exceptions.HTTPError(
                f"{str(e)}{error_detail}", response=response
            ) from e

    def begin_analyze_binary(
        self, 
        file_bytes: bytes, 
        analyzer_id: str = None
    ) -> requests.Response:
        """
        Begin analysis of binary file content.
        
        Args:
            file_bytes: The file content as bytes
            analyzer_id: The analyzer to use (default: prebuilt-documentSearch)
            
        Returns:
            Response object containing operation location for polling
        """
        if analyzer_id is None:
            analyzer_id = self.PREBUILT_DOCUMENT_ANALYZER_ID
            
        headers = {"Content-Type": "application/octet-stream"}
        headers.update(self._headers)
        
        response = requests.post(
            url=self._get_analyze_binary_url(analyzer_id),
            headers=headers,
            data=file_bytes,
        )
        
        self._raise_for_status_with_detail(response)
        self._logger.info(f"Analyzing binary with analyzer: {analyzer_id}")
        return response

    def begin_analyze_url(
        self, 
        url: str, 
        analyzer_id: str = None
    ) -> requests.Response:
        """
        Begin analysis of a document from URL.
        
        Args:
            url: The URL of the document to analyze
            analyzer_id: The analyzer to use (default: prebuilt-documentSearch)
            
        Returns:
            Response object containing operation location for polling
        """
        if analyzer_id is None:
            analyzer_id = self.PREBUILT_DOCUMENT_ANALYZER_ID
            
        if not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("URL must start with http:// or https://")
        
        data = {"inputs": [{"url": url}]}
        headers = {"Content-Type": "application/json"}
        headers.update(self._headers)
        
        response = requests.post(
            url=self._get_analyze_url(analyzer_id),
            headers=headers,
            json=data,
        )
        
        self._raise_for_status_with_detail(response)
        self._logger.info(f"Analyzing URL {url} with analyzer: {analyzer_id}")
        return response

    def poll_result(
        self,
        response: requests.Response,
        timeout_seconds: int = POLL_TIMEOUT_SECONDS,
        polling_interval_seconds: int = 2,
    ) -> Dict[str, Any]:
        """
        Poll for the analysis result.
        
        Args:
            response: The response from begin_analyze_* method
            timeout_seconds: Maximum time to wait for completion
            polling_interval_seconds: Time between polling attempts
            
        Returns:
            The analysis result as a dictionary
        """
        operation_location = response.headers.get("operation-location", "")
        if not operation_location:
            raise ValueError(
                "Operation location not found in the analyzer response header."
            )

        start_time = time.time()
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                raise TimeoutError(
                    f"Operation timed out after {timeout_seconds:.2f} seconds."
                )

            poll_response = requests.get(operation_location, headers=self._headers)
            self._raise_for_status_with_detail(poll_response)
            
            result = poll_response.json()
            status = result.get("status", "").lower()
            
            if status == "succeeded":
                self._logger.info(
                    f"Request completed after {elapsed_time:.2f} seconds."
                )
                return result
            elif status == "failed":
                self._logger.error(f"Request failed. Response: {result}")
                raise RuntimeError(f"Analysis failed: {result}")
            else:
                self._logger.debug(f"Status: {status}, waiting...")
                time.sleep(polling_interval_seconds)

    def analyze_document(
        self, 
        file_bytes: bytes,
        analyzer_id: str = None,
    ) -> Dict[str, Any]:
        """
        Analyze a document and return the result.
        
        This is a convenience method that combines begin_analyze_binary and poll_result.
        
        Args:
            file_bytes: The document content as bytes
            analyzer_id: The analyzer to use (default: prebuilt-documentSearch)
            
        Returns:
            The analysis result as a dictionary
        """
        response = self.begin_analyze_binary(file_bytes, analyzer_id)
        return self.poll_result(response)

    def extract_markdown(self, result: Dict[str, Any]) -> str:
        """
        Extract markdown content from analysis result.
        
        Args:
            result: The analysis result from poll_result
            
        Returns:
            The extracted markdown content
        """
        contents = result.get("result", {}).get("contents", [])
        if contents:
            return contents[0].get("markdown", "")
        return ""
