from collections import Counter
from app.config import styles


def count_by_path(secrets: dict):
  return dict(Counter([secret['secretPath'] for secret in secrets]))


def list_folders_secrets(folders, secrets):
  by_id = {f['id']: f for f in (folders or [])}
  path_cache: dict[str, str] = {}

  def get_folder_path(folder):
    fid = folder['id']
    if fid in path_cache:
      return path_cache[fid]

    parts = [folder.get('name', '').strip('/') or '']
    parent_id = folder.get('parentId')

    while parent_id and parent_id in by_id:
      parent = by_id[parent_id]
      parts.append(parent.get('name', '').strip('/') or '')
      parent_id = parent.get('parentId')

    parts = [p for p in reversed(parts) if p]
    path = '/' + '/'.join(parts)
    if not parts:
      path = '/'
    path_cache[fid] = path
    return path

  all_paths: set[str] = set(['/'])

  for f in folders or []:
    p = get_folder_path(f)
    if not p.startswith('/'):
      p = '/' + p
    p = p.rstrip('/') or '/'
    all_paths.add(p)

  direct_counts: dict[str, int] = {}

  for s in secrets or []:
    spath = s.get('secretPath') or '/'
    if not spath.startswith('/'):
      spath = '/' + spath
    spath = spath.rstrip('/') or '/'
    direct_counts[spath] = direct_counts.get(spath, 0) + 1
    all_paths.add(spath)

  result: dict[str, int] = {}
  for p in sorted(all_paths):
    result[p] = direct_counts.get(p, 0)

  return result


def key(k, padding=None, style_override=None, literal=False):
  """
  k: клавиша (Enter, enter, ESC, esc...)
  literal: если True — не преобразовывать в символы вообще.
  """

  KEY_SYMBOLS = {
    'enter': '↩',
    'return': '↩',
    'backspace': '⌫',
    'delete': '⌫',
    'esc': '⎋',
    'escape': '⎋',
    'tab': '⇥',
    'shift': '⇧',
    'ctrl': '⌃',
    'control': '⌃',
    'alt': '⌥',
    'option': '⌥',
    'cmd': '⌘',
    'command': '⌘',
    'space': '␠',
    'up': '↑',
    'down': '↓',
    'left': '←',
    'right': '→'
  }

  style = style_override or styles.get('key', 'black on gray')

  if padding is None:
    padding = styles.get('key_padding', None)

  key_raw = str(k).strip()

  # --- 1) literal mode → ничего не трогаем ---
  if literal:
    pretty_key = key_raw

  # --- 2) exact symbol substitution ONLY if lowercase key matches ---
  else:
    mapped = KEY_SYMBOLS.get(key_raw.lower())

    if mapped and key_raw.islower():
      # заменяем только если "enter" → символ
      pretty_key = mapped
    else:
      # иначе выводим как есть: Enter, Delete, SPACE, etc
      pretty_key = key_raw

  pad_first, pad_last = {
    'space': (' ', ' '),
    'dash': ('-', '-'),
    'bracket': ('[', ']'),
    None: ('', ''),
  }.get(padding, ('', ''))

  return f'[{style}]{pad_first}{pretty_key}{pad_last}[/]'