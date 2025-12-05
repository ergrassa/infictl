import httpx

from app.config import config

api = httpx.AsyncClient(http2=False)
api.base_url = config['api']['url']


async def get(path):
  return await api.get(path)


async def post(path, data):
  return await api.post(path, json=data)
