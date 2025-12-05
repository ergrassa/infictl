from app.http import get
from app.config import config
from httpx import RequestError, HTTPStatusError


async def get_workspaces():
  url = f"/api/v2/organizations/{config['api']['org_id']}/workspaces"
  try:
    response = await get(url)
    response.raise_for_status()
    return response.json()
  except (RequestError, HTTPStatusError, ValueError):
    return []
