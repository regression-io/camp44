"""
Base44 integrations proxy endpoints.

Proxies requests to Base44's Core integrations (InvokeLLM, SendEmail, etc.)
using the service API key, so users authenticate to camp44 and never see
the Base44 credentials.

Also supports auth proxy mode (BASE44_AUTH_PROXY=true) where auth is proxied
to Base44 for users who want to use Base44 accounts with self-hosted infrastructure.
"""

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from camp44.api import deps
from camp44.core.config import settings
from camp44.models.user import User

logger = logging.getLogger(__name__)

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
            detail="Base44 integration not configured. Set BASE44_API_KEY.",
        )
    if not settings.BASE44_APP_ID:
        raise HTTPException(
            status_code=503,
            detail="Base44 integration not configured. Set BASE44_APP_ID.",
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
                logger.error(
                    "Base44 %s error (HTTP %d): %s",
                    integration_name,
                    response.status_code,
                    response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"{integration_name} request failed",
                )

            return response.json()

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504, detail=f"{integration_name} request timed out"
            )
        except httpx.RequestError as e:
            logger.error("Base44 %s connection error: %s", integration_name, e)
            raise HTTPException(
                status_code=502, detail=f"{integration_name} service unavailable"
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
    # Testing safety: redirect outbound emails to the logged-in user
    # so test emails never reach real recipients.
    # Only active when TESTING=1 (never in production).
    from camp44.core.config import settings

    if getattr(settings, "TESTING", False) and "to" in request:
        request = {
            **request,
            "to": _current_user.email,
            "subject": f"[REDIRECTED] {request.get('subject', '')}",
        }
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


# =============================================================================
# Auth Proxy Endpoints (when BASE44_AUTH_PROXY=true)
# =============================================================================


@router.get("/auth/login")
async def auth_proxy_login(
    request: Request,
    from_url: Optional[str] = None,
    app_id: Optional[str] = None,
):
    """
    Redirect to Base44 login page when BASE44_AUTH_PROXY is enabled.
    Otherwise returns 404 (use /auth/login for local auth).
    """
    if not settings.BASE44_AUTH_PROXY:
        raise HTTPException(
            status_code=404,
            detail="Base44 auth proxy not enabled. Use /auth/login for local auth.",
        )

    _check_base44_config()

    # Build Base44 login URL with redirect back to camp44
    from_url = from_url or str(request.query_params.get("from_url", ""))
    app_id = app_id or settings.BASE44_APP_ID

    base44_login_url = f"{settings.BASE44_API_URL.replace('/api', '')}/login"
    params = []
    if from_url:
        params.append(f"from_url={from_url}")
    if app_id:
        params.append(f"app_id={app_id}")

    if params:
        base44_login_url += "?" + "&".join(params)

    return RedirectResponse(url=base44_login_url, status_code=302)


@router.get("/auth/me")
async def auth_proxy_me(
    request: Request,
) -> Any:
    """
    Proxy /users/me to Base44 when BASE44_AUTH_PROXY is enabled.
    Uses the token from Authorization header.
    """
    if not settings.BASE44_AUTH_PROXY:
        raise HTTPException(
            status_code=404,
            detail="Base44 auth proxy not enabled. Use /users/me for local auth.",
        )

    _check_base44_config()

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{settings.BASE44_API_URL}/users/me",
                headers={
                    "Authorization": auth_header,
                    "X-App-Id": settings.BASE44_APP_ID or "",
                },
            )

            if response.status_code != 200:
                logger.error(
                    "Base44 auth /me error (HTTP %d): %s",
                    response.status_code,
                    response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Authentication request failed",
                )

            return response.json()

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504, detail="Authentication request timed out"
            )
        except httpx.RequestError as e:
            logger.error("Base44 auth /me connection error: %s", e)
            raise HTTPException(
                status_code=502, detail="Authentication service unavailable"
            )


@router.patch("/auth/me")
async def auth_proxy_update_me(
    request: Request,
    body: Dict[str, Any],
) -> Any:
    """
    Proxy PATCH /users/me to Base44 when BASE44_AUTH_PROXY is enabled.
    Used for updating user profile (e.g., onboarding_complete).
    """
    if not settings.BASE44_AUTH_PROXY:
        raise HTTPException(
            status_code=404,
            detail="Base44 auth proxy not enabled. Use /users/me for local auth.",
        )

    _check_base44_config()

    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header required")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.patch(
                f"{settings.BASE44_API_URL}/users/me",
                headers={
                    "Authorization": auth_header,
                    "X-App-Id": settings.BASE44_APP_ID or "",
                    "Content-Type": "application/json",
                },
                json=body,
            )

            if response.status_code != 200:
                logger.error(
                    "Base44 auth PATCH /me error (HTTP %d): %s",
                    response.status_code,
                    response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail="Authentication request failed",
                )

            return response.json()

        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504, detail="Authentication request timed out"
            )
        except httpx.RequestError as e:
            logger.error("Base44 auth PATCH /me connection error: %s", e)
            raise HTTPException(
                status_code=502, detail="Authentication service unavailable"
            )
