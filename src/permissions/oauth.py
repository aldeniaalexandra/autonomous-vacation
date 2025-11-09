import os
from typing import Dict, Any

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request


def get_oauth() -> OAuth:
    oauth = OAuth()
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
    # Configure Google as example provider; app can extend to others
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile https://www.googleapis.com/auth/calendar"},
    )
    return oauth


async def get_authorization_url(request: Request) -> str:
    oauth = get_oauth()
    redirect_uri = os.getenv("OAUTH_REDIRECT_URI")
    return await oauth.google.authorize_redirect(request, redirect_uri)


async def exchange_code(request: Request) -> Dict[str, Any]:
    oauth = get_oauth()
    token = await oauth.google.authorize_access_token(request)
    return token