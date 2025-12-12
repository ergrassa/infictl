from httpx import RequestError, HTTPStatusError

from app.config import config
from app.http import get, post, delete, patch

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


async def list_folders(workspace_id, environment_slug, recursive=True):
  url = '/api/v1/folders'
  query_params = {
    'workspaceId': workspace_id,
    'environment': environment_slug,
    'recursive': recursive
  }
  try:
    response = await get(url, params=query_params)
    response.raise_for_status()
    data = response.json()
    return data.get('folders', [])
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to list folders: {e}")
    return []


async def get_secrets(
  workspace_id,
  environment_slug,
  secret_path='/',
  recursive=False,
  reveal=False
  ):
  url = '/api/v3/secrets/raw'
  query_params = {
    'workspaceId': workspace_id,
    'environment': environment_slug,
    'secretPath': secret_path,
    'recursive': recursive,
    'viewSecretValue': reveal
  }
  try:
    response = await get(url, params=query_params)
    response.raise_for_status()
    data = response.json()
    return data.get('secrets', [])
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to get secrets: {e}")
    return []


async def create_folder(
  workspace_id,
  environment_slug,
  folder_name,
  folder_path='/',
  folder_description=''
  ):
  url = '/api/v1/folders'
  data = {
    'workspaceId': workspace_id,
    'environment': environment_slug,
    'name': folder_name,
    'path': folder_path,
    'description': folder_description
  }
  try:
    response = await post(url, data=data)
    response.raise_for_status()
    return response.json()
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to create folder: {e}")
    return {}


async def delete_folder(
  workspace_id,
  environment_slug,
  folder_name,
  folder_path='/',
  ):
  url = f"/api/v1/folders/{folder_name}"
  data = {
    'workspaceId': workspace_id,
    'environment': environment_slug,
    'path': folder_path
  }
  try:
    response = await delete(url, data=data)
    response.raise_for_status()
    return response.json()
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to delete folder: {e}")
    return {}


async def create_environment(
  workspace_id,
  environment_name,
  environment_slug
  ):
  url = f"api/v1/workspace/{workspace_id}/environments"
  data = {
    'name': environment_name,
    'slug': environment_slug
  }
  try:
    response = await post(url, data=data)
    response.raise_for_status()
    return response.json()
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to create environment: {e}")
    return {}


async def delete_environment(
  workspace_id,
  environment_id
  ):
  url = f"api/v1/workspace/{workspace_id}/environments/{environment_id}"
  try:
    response = await delete(url)
    response.raise_for_status()
    return response.json()
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to delete environment: {e}")
    return {}


async def create_secrets_bulk(
  workspace_id,
  environment_slug,
  secrets_path,
  secrets: dict
  ):
  url = '/api/v3/secrets/batch/raw'
  secrets_fmt = [
    {
      'secretKey': k,
      'secretValue': v
    }
    for k, v in secrets.items()
  ]
  data = {
    'workspaceId': workspace_id,
    'environment': environment_slug,
    'secretPath': secrets_path,
    'secrets': secrets_fmt
  }
  try:
    response = await post(url, data=data)
    response.raise_for_status()
    return response.json()
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to create secrets: {e}")
    return {}


async def update_secrets_bulk(
  workspace_id,
  environment_slug,
  secrets_path,
  secrets: dict
  ):
  url = '/api/v3/secrets/batch/raw'
  secrets_fmt = [
    {
      'secretKey': k,
      'secretValue': v
    }
    for k, v in secrets.items()
  ]
  data = {
    'workspaceId': workspace_id,
    'environment': environment_slug,
    'secretPath': secrets_path,
    'secrets': secrets_fmt
  }
  try:
    response = await patch(url, data=data)
    response.raise_for_status()
    return response.json()
  except (RequestError, HTTPStatusError, ValueError, TypeError, KeyError) as e:
    logging.error(f"Failed to update secrets: {e}")
    return {}


