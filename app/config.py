import tomllib

CONFIG_FILES = [
  'config.toml',
  '~/.config/infictl/config.toml'
]

STYLES_FILES = [
  'styles.toml',
  '~/.config/infictl/styles.toml'
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


def loat_styles():
  for styles_file in STYLES_FILES:
    print(f"Trying {styles_file}")
    try:
      with open(styles_file, 'rb') as f:
        styles = tomllib.load(f)
        return styles
    except FileNotFoundError:
      pass
  return {}


config = load_config()
styles = loat_styles()
