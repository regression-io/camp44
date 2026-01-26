"""Base44 integrations proxy endpoints.

Proxies requests to Base44's Core integrations (InvokeLLM, SendEmail, etc.)
using the service API key, so users authenticate to camp44 and never see
the Base44 credentials.
"""
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends, HTTPException

from camp44.api import deps
from camp44.core.config import settings
from camp44.models.user import User

router = APIRouter()

# Supported Core integrations that can be proxied to Base44
SUPPORTED_INTEGRATIONS = {
    "InvokeLLM",
    "SendEmail",
    "SendSMS",
    "GenerateImage",
    "ExtractDataFromUploadedFile",
}


def _check_base44_config():
    """Verify Base44 credentials are configured."""
    if not settings.BASE44_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Base44 integration not configured. Set BASE44_API_KEY."
        )
    if not settings.BASE44_APP_ID:
        raise HTTPException(
            status_code=503,
            detail="Base44 integration not configured. Set BASE44_APP_ID."
        )


async def _proxy_to_base44(
    integration_name: str,
    payload: Dict[str, Any],
    timeout: float = 120.0,
) -> Any:
    """Proxy a request to Base44's integration endpoint."""
    _check_base44_config()

    # After check, these are guaranteed to be set
    api_key: str = settings.BASE44_API_KEY  # type: ignore[assignment]
    app_id: str = settings.BASE44_APP_ID  # type: ignore[assignment]

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                f"{settings.BASE44_API_URL}/apps/{app_id}/integration-endpoints/Core/{integration_name}",
                headers={
                    "Content-Type": "application/json",
                    "api_key": api_key,
                },
                json=payload,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Base44 {integration_name} error: {response.text}"
                )

            return response.json()

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail=f"{integration_name} request timed out"
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Base44: {str(e)}"
            )


@router.post("/invoke")
async def invoke_llm(
    request: Dict[str, Any],
    _current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Proxy LLM requests to Base44's InvokeLLM.

    Accepts: prompt, response_json_schema, add_context_from_internet, model, max_tokens, temperature
    """
    return await _proxy_to_base44("InvokeLLM", request)


@router.post("/send-email")
async def send_email(
    request: Dict[str, Any],
    _current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Proxy email requests to Base44's SendEmail.

    Accepts: to, subject, body, from_email, etc.
    """
    return await _proxy_to_base44("SendEmail", request)


@router.post("/send-sms")
async def send_sms(
    request: Dict[str, Any],
    _current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Proxy SMS requests to Base44's SendSMS.

    Accepts: to, message, etc.
    """
    return await _proxy_to_base44("SendSMS", request)


@router.post("/generate-image")
async def generate_image(
    request: Dict[str, Any],
    _current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Proxy image generation requests to Base44's GenerateImage.

    Accepts: prompt, size, style, etc.
    """
    return await _proxy_to_base44("GenerateImage", request)


@router.post("/extract-data")
async def extract_data_from_file(
    request: Dict[str, Any],
    _current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Proxy file data extraction requests to Base44's ExtractDataFromUploadedFile.

    Accepts: file_url, extraction_schema, etc.
    """
    return await _proxy_to_base44("ExtractDataFromUploadedFile", request)
