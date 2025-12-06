from httpx import RequestError, HTTPStatusError

from app.config import config
from app.http import get

import logging


async def get_workspaces():
  url = f"/api/v2/organizations/{config['api']['org_id']}/workspaces"
  try:
    response = await get(url)
    response.raise_for_status()
    data = response.json()
    return data.get('workspaces', [])
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to get workspaces: {e}")
    return []


async def list_folders(workspace_id, environment_slug):
  url = '/api/v1/folders'
  query_params = {
    'workspaceId': workspace_id,
    'environment': environment_slug
  }
  try:
    response = await get(url, params=query_params)
    response.raise_for_status()
    data = response.json()
    return data.get('folders', [])
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to list folders: {e}")
    return []
