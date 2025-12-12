# app/http.py
import httpx

from app.config import config

api_config = config.get('api', {})

api = httpx.AsyncClient(
  http2=False,
  base_url=api_config.get('url', '')
)

api.token = api_config.get('token', '')
headers = {
  'Authorization': f'Bearer {api.token}'
}


async def get(path, params=None):
  response = await api.get(path, headers=headers, params=params)
  return response


async def post(path, data, params=None):
  response = await api.post(path, json=data, headers=headers, params=params)
  return response


async def delete(path, data=None, params=None):
  response = await api.request('DELETE', path, data=data, headers=headers, params=params)
  return response


async def patch(path, data, params=None):
  response = await api.patch(path, json=data, headers=headers, params=params)
  return response

