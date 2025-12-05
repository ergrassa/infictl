import tomllib

CONFIG_FILES = [
  'config.toml',
  '~/.config/infictl/config.toml'
]


def load_config():
  for config_file in CONFIG_FILES:
    print(f"Trying {config_file}")
    try:
      with open(config_file, 'rb') as f:
        config = tomllib.load(f)
        return config
    except FileNotFoundError:
      pass
  return {}


config = load_config()
