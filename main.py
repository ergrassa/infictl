import logging

from rich.text import Text

from textual.app import App
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Static, OptionList, Input, Tree, DataTable, Button, TextArea, Checkbox
from textual.widgets.option_list import Option

from app.api import (
  get_workspaces,
  get_secrets,
  create_folder,
  list_folders,
  delete_folder,
  create_environment,
  delete_environment,
  create_secrets_bulk,
  update_secrets_bulk,
  delete_secrets_bulk,
)
from app.func import list_folders_secrets, key
from app.config import styles


logging.basicConfig(
  level=logging.DEBUG,
  format='%(name)s - %(levelname)s - %(message)s',
  filename='infictl.log',
  filemode='w'
)


class WorkspaceList(OptionList):
  pass


class WorkspaceSelectScreen(Screen):
  def compose(self):
    yield Static('Select workspace:', id='ws-title')
    yield WorkspaceList()
    yield Footer()

  def on_mount(self) -> None:
    option_list = self.query_one(WorkspaceList)
    option_list.clear_options()
    option_list.add_option(
      Option('⌛ Loading...', id='loading', disabled=True)
    )
    self.run_worker(self.load_workspaces(), exclusive=True)

  async def load_workspaces(self) -> None:
    option_list = self.query_one(WorkspaceList)

    try:
      workspaces = await get_workspaces()

      option_list.clear_options()

      if not workspaces:
        option_list.add_option(
          Option('⚠️ No workspaces found', disabled=True)
        )
        return

      app = self.app
      if isinstance(app, InfictlApp):
        app.workspaces_by_id.clear()
        for ws in workspaces:
          app.workspaces_by_id[ws['id']] = ws

      for ws in workspaces:
        text = Text()
        text.append(ws['name'], style=styles.get('workspace_name', 'yellow'))
        text.append(' ')
        text.append(
          f'({ws["slug"]})',
          style=styles.get('workspace_slug', 'grey50')
        )

        option_list.add_option(Option(text, id=ws['id']))

    except Exception as e:
      logging.error(f'Failed to get workspaces: {e}')
      option_list.clear_options()
      option_list.add_option(
        Option('⚠️ Failed to load workspaces', disabled=True)
      )


class EditSecretValueScreen(Screen):
  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
    ('enter', 'apply', 'Apply'),
  ]

  def __init__(self, key_name: str, value: str):
    super().__init__()
    self.key_name = key_name
    self.value = value

  def compose(self):
    key_color = styles.get('key_name', styles.get('folder_count', 'white'))
    esc_key = key('Esc')
    enter_key = key('Enter', literal=True)

    yield Static(
      f'Edit value for [{key_color}]{self.key_name}[/]',
      id='sv-title'
    )
    yield Input(value=self.value, id='sv-input')
    yield Static(
      f'Press {enter_key} to apply, {esc_key} to cancel.',
      id='sv-hint'
    )
    yield Footer()

  def on_mount(self) -> None:
    self.query_one('#sv-input', Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == 'sv-input':
      self.action_apply()

  def action_cancel(self):
    self.app.pop_screen()

  def action_apply(self):
    inp = self.query_one('#sv-input', Input)
    value = inp.value
    app = self.app

    # Close this screen first, then apply the edit after the previous screen is active.
    app.pop_screen()

    if isinstance(app, InfictlApp):
      # Give Textual a moment to finish the screen transition.
      app.set_timer(0.05, lambda: app._apply_secret_value_edit(self.key_name, value))


class AddSecretScreen(Screen):
  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
    ('enter', 'apply', 'Apply'),
  ]

  def compose(self):
    key_color = styles.get('key_name', 'white')
    esc_key = key('Esc')
    enter_key = key('Enter', literal=True)

    yield Static('Add new secret', id='as-title')
    yield Static('Key:', id='as-key-label')
    yield Input(id='as-key')
    yield Static('Value:', id='as-value-label')
    yield Input(id='as-value')
    yield Static(
      f'Press {enter_key} to add, {esc_key} to cancel.',
      id='as-hint'
    )
    yield Footer()

  def on_mount(self) -> None:
    self.query_one('#as-key', Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    # Enter on Key moves to Value, Enter on Value applies
    if event.input.id == 'as-key':
      self.query_one('#as-value', Input).focus()
      return

    if event.input.id == 'as-value':
      self.action_apply()

  def action_cancel(self):
    self.app.pop_screen()

  def action_apply(self):
    key_input = self.query_one('#as-key', Input)
    val_input = self.query_one('#as-value', Input)

    k = key_input.value.strip()
    v = val_input.value

    if not k:
      self.app.bell()
      return

    self.app.pop_screen()

    app = self.app
    if isinstance(app, InfictlApp):
      app.set_timer(
        0.05,
        lambda: app._apply_new_secret(k, v)
      )


# BulkAddSecretsScreen: bulk add secrets from K=V lines
class BulkAddSecretsScreen(Screen):
  """Bulk add secrets from multiline K=V pairs.

  - One line = one pair.
  - Separator = FIRST '='.
  - Enter inserts newline (TextArea default).
  - To add: move focus to the Add button and press it.
  """

  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
  ]

  def compose(self):
    esc_key = key('Esc')

    yield Static('Bulk add secrets (one per line: K=V)', id='ba-title')
    yield TextArea(
      id='ba-text',
      placeholder='EXAMPLE_KEY=value\nANOTHER_KEY=another value\nEMPTY_VALUE=\n',
    )
    yield Static(
      f'Enter = newline. Use Tab/Shift+Tab to focus the Add button. {esc_key} cancel.',
      id='ba-hint'
    )
    with Horizontal(id='ba-buttons'):
      yield Button('Add', id='ba-add', variant='primary')
      yield Button('Cancel', id='ba-cancel')
    yield Footer()

  def on_mount(self) -> None:
    self.query_one('#ba-text', TextArea).focus()

  def action_cancel(self):
    self.app.pop_screen()

  def on_button_pressed(self, event: Button.Pressed) -> None:
    if event.button.id == 'ba-cancel':
      self.action_cancel()
      return

    if event.button.id != 'ba-add':
      return

    text_area = self.query_one('#ba-text', TextArea)
    raw = (text_area.text or '').strip('\n')
    if not raw.strip():
      self.app.bell()
      return

    pairs: list[tuple[str, str]] = []
    for line in raw.splitlines():
      s = line.strip()
      if not s:
        continue
      if '=' not in s:
        continue
      k, v = s.split('=', 1)
      k = k.strip()
      if not k:
        continue
      pairs.append((k, v))

    if not pairs:
      self.app.bell()
      return

    # Close this screen first, then apply the bulk add after returning to SecretsScreen
    self.app.pop_screen()

    app = self.app
    if isinstance(app, InfictlApp):
      app.set_timer(0.05, lambda: app._apply_bulk_new_secrets(pairs))


class SecretsScreen(Screen):
  '''Экран просмотра/редактирования секретов в папке.'''

  BINDINGS = [
    ('escape', 'close', 'Close'),
    ('e', 'allow_edit', 'Allow edit'),
    ('enter', 'edit_value', 'Edit value'),
    ('x', 'toggle_delete', 'Mark delete'),
    ('s', 'save', 'Save'),
    ('v', 'noop', 'Noop'),
    ('a', 'add_secret', 'Add secret'),
    ('b', 'bulk_add', 'Bulk add'),
  ]
  def action_add_secret(self):
    if not (self._edit_enabled and self._revealed):
      self.app.bell()
      return

    self.app.push_screen(AddSecretScreen())

  def action_bulk_add(self):
    if not (self._edit_enabled and self._revealed):
      self.app.bell()
      return

    self.app.push_screen(BulkAddSecretsScreen())

  DEFAULT_CSS = '''
  SecretsScreen {
    align-horizontal: left;
    align-vertical: top;
  }
  #secrets-table {
    overflow-x: hidden;
  }
  '''

  def __init__(self, workspace_id: str, env_slug: str, folder_path: str):
    super().__init__()
    self.workspace_id = workspace_id
    self.env_slug = env_slug
    self.folder_path = folder_path or '/'
    self._revealed = False
    self._edit_enabled = False
    self._original: dict[str, str] = {}
    self._current: dict[str, str] = {}
    self._changed: set[str] = set()
    self._deleted: set[str] = set()
    self._row_index_by_key: dict[str, int] = {}
    self._cursor_key: str | None = None

  def compose(self):
    title_color = styles.get('folder_name', 'bright_yellow')
    env_color = styles.get('env_name', 'cyan')
    key_style = styles.get('key', 'black on gray')

    esc_key = key('Esc', style_override=key_style)
    e_key = key('e', style_override=key_style)
    s_key = key('s', style_override=key_style)
    x_key = key('x', style_override=key_style)
    enter_key = key('Enter', style_override=key_style, literal=True)

    yield Static(
      f'[{env_color}]{self.env_slug}[/]  '
      f'[{title_color}]{self.folder_path}[/]',
      id='secrets-title'
    )
    # Add Ch column meaning (optional) to hint line, but keep hotkeys.
    yield Static(
      f'{esc_key} close   {e_key} allow edit   {enter_key} edit value   {x_key} mark delete   {s_key} save',
      id='secrets-hint'
    )
    yield DataTable(id='secrets-table')
    yield Footer()

  def on_mount(self) -> None:
    self._render_loading('Loading keys...')
    self.run_worker(self._load_secrets(reveal=False), exclusive=True)

  def action_noop(self):
    return

  def action_close(self):
    self.app.pop_screen()

  def action_allow_edit(self):
    if self._revealed and self._edit_enabled:
      return
    self._edit_enabled = True
    self._render_loading('Loading values...')
    self.run_worker(self._load_secrets(reveal=True), exclusive=True)

  def action_edit_value(self):
    if not (self._edit_enabled and self._revealed):
      self.app.bell()
      return

    table = self.query_one('#secrets-table', DataTable)
    if table.row_count == 0:
      self.app.bell()
      return

    # --- Determine cursor position (Textual versions differ) ---
    row_index: int | None = None
    col_index: int | None = None

    if hasattr(table, 'cursor_row') and hasattr(table, 'cursor_column'):
      try:
        row_index = int(getattr(table, 'cursor_row'))
        col_index = int(getattr(table, 'cursor_column'))
      except Exception:
        row_index = None
        col_index = None

    if (row_index is None or col_index is None) and hasattr(table, 'cursor_coordinate'):
      try:
        coord = getattr(table, 'cursor_coordinate')
        row_index = int(getattr(coord, 'row'))
        col_index = int(getattr(coord, 'column'))
      except Exception:
        row_index = None
        col_index = None

    if row_index is None or col_index is None:
      self.app.bell()
      return

    # Edit only VALUE column (now at index 2)
    if col_index != 2:
      self.app.bell()
      return

    # --- Resolve row key (Textual versions differ) ---
    row_key = self._get_cursor_secret_key()
    if not row_key:
      self.app.bell()
      return

    if row_key in self._deleted:
      self.app.bell()
      return

    current_value = self._current.get(row_key, '')
    self.app.push_screen(EditSecretValueScreen(row_key, current_value))

  def action_toggle_delete(self):
    if not (self._edit_enabled and self._revealed):
      self.app.bell()
      return

    row_key = self._get_cursor_secret_key()
    if not row_key:
      self.app.bell()
      return

    if row_key in self._deleted:
      self._deleted.discard(row_key)
    else:
      self._deleted.add(row_key)
      self._changed.discard(row_key)

    self._rerender_from_state()
    self._update_hint(reveal=self._revealed, saved=None)

  def on_key(self, event) -> None:
    # DataTable consumes Enter; intercept it for inline editing when table is focused
    try:
      focused = self.app.focused
    except Exception:
      focused = None

    if event.key == 'enter' and focused is not None and getattr(focused, 'id', None) == 'secrets-table':
      self.action_edit_value()
      try:
        event.prevent_default()
        event.stop()
      except Exception:
        pass

  def action_save(self):
    if not self._edit_enabled:
      self.app.bell()
      return

    to_create = {
      k: v for k, v in self._current.items()
      if k not in self._original
    }
    to_update = {
      k: v for k, v in self._current.items()
      if k in self._original and v != self._original.get(k)
    }
    to_delete = sorted(self._deleted)

    # Do not create/update keys marked for deletion
    for k in list(to_create.keys()):
      if k in self._deleted:
        to_create.pop(k, None)
    for k in list(to_update.keys()):
      if k in self._deleted:
        to_update.pop(k, None)
    if not to_create and not to_update and not to_delete:
      hint = self.query_one('#secrets-hint', Static)
      hint.update('[dim]No changes to save[/]')

      self.set_timer(
        1.5,
        lambda: self.app.call_after_refresh(
          lambda: self._update_hint(reveal=self._revealed, saved=None)
        )
      )
      return

    self._render_loading('Saving...')
    self.run_worker(
      self._save_changes(to_create, to_update, to_delete),
      exclusive=True
    )

  def _get_cursor_secret_key(self) -> str | None:
    """Return the secret key for the currently highlighted row.

    Prefer an event-tracked key (most reliable), then fall back to querying DataTable.
    """

    # 1) Most reliable: tracked from highlight events
    if self._cursor_key:
      return self._cursor_key

    table = self.query_one('#secrets-table', DataTable)
    if table.row_count == 0:
      return None

    # 2) Determine cursor row index (Textual versions differ)
    row_index: int | None = None
    if hasattr(table, 'cursor_row'):
      try:
        row_index = int(getattr(table, 'cursor_row'))
      except Exception:
        row_index = None

    if row_index is None and hasattr(table, 'cursor_coordinate'):
      try:
        coord = getattr(table, 'cursor_coordinate')
        row_index = int(getattr(coord, 'row'))
      except Exception:
        row_index = None

    if row_index is None:
      return None

    # 3) Prefer row keys if supported (we add rows with key=k)
    if hasattr(table, 'row_keys'):
      try:
        keys = list(getattr(table, 'row_keys'))
        if 0 <= row_index < len(keys):
          return str(keys[row_index])
      except Exception:
        pass

    if hasattr(table, 'get_row_key'):
      try:
        return str(table.get_row_key(row_index))
      except Exception:
        pass

    # 4) Fallback: read the KEY column (index 1, because col0 is ✎)
    try:
      row = table.get_row_at(row_index)
      if row and len(row) > 1:
        return str(row[1])
    except Exception:
      pass

    return None

  def _rerender_from_state(self) -> None:
    """Rebuild the DataTable from in-memory state.

    This is the most compatible way to ensure the UI reflects edits immediately
    across different Textual versions (avoids relying on update_cell_at APIs).
    """
    table = self.query_one('#secrets-table', DataTable)

    table.clear(columns=True)
    table.add_column('✎', key='changed')
    table.add_column('KEY', key='key')
    table.add_column('VALUE', key='value')
    self._configure_table_columns()

    self._row_index_by_key = {}
    self._cursor_key = None

    keys = sorted(self._current.keys(), key=lambda x: str(x).lower())
    if not keys:
      table.add_row('', '', Text('No secrets in this folder', overflow='fold', no_wrap=False))
      table.refresh(layout=False)
      return

    for k in keys:
      v = self._current.get(k, '')
      value_str = str(v) if self._revealed else '<hidden>'
      if k in self._deleted:
        changed_mark = 'X'
      elif k in self._changed:
        changed_mark = '*'
      else:
        changed_mark = ''
      value_cell = Text(value_str, overflow='fold', no_wrap=False)
      table.add_row(changed_mark, k, value_cell, key=k)
      try:
        self._row_index_by_key[k] = table.row_count - 1
      except Exception:
        pass

    try:
      table.refresh(layout=False)
    except Exception:
      pass

  def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
    # Track which secret row is highlighted (most reliable across Textual versions)
    rk = getattr(event, 'row_key', None)
    if rk is not None:
      self._cursor_key = str(rk)
    else:
      # Fallback: pull from KEY column (index 1)
      try:
        table = self.query_one('#secrets-table', DataTable)
        row = table.get_row_at(int(getattr(event, 'row')))
        if row and len(row) > 1:
          self._cursor_key = str(row[1])
      except Exception:
        pass

    self._update_hint(reveal=self._revealed, saved=None)

  def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
    rk = getattr(event, 'row_key', None)
    if rk is not None:
      self._cursor_key = str(rk)
    else:
      # Fallback: read KEY column (index 1)
      try:
        table = self.query_one('#secrets-table', DataTable)
        row = table.get_row_at(int(getattr(event, 'row')))
        if row and len(row) > 1:
          self._cursor_key = str(row[1])
      except Exception:
        pass

    self._update_hint(reveal=self._revealed, saved=None)

  def _configure_table_columns(self) -> None:
    table = self.query_one('#secrets-table', DataTable)

    # Bound the widget itself
    table.styles.width = '90%'

    # Best-effort fixed widths (Textual versions differ; only apply if supported)
    def _apply_widths() -> None:
      try:
        avail = int(getattr(table, 'size').width)
      except Exception:
        try:
          avail = int(getattr(self.app, 'size').width * 0.90)
        except Exception:
          avail = 120

      # Reserve a little room for borders / padding
      avail = max(30, avail - 4)

      ch_w = 2
      key_w = max(10, int(avail * 0.25))
      val_w = max(10, avail - ch_w - key_w)

      # Some Textual builds expose set_column_width
      if hasattr(table, 'set_column_width'):
        try:
          table.set_column_width(0, ch_w)
          table.set_column_width(1, key_w)
          table.set_column_width(2, val_w)
        except Exception:
          pass

    # Apply after layout so size.width is valid
    self.call_after_refresh(_apply_widths)

  def _render_loading(self, msg: str):
    def _do():
      table = self.query_one('#secrets-table', DataTable)
      table.clear(columns=True)
      table.add_column('✎', key='changed')
      table.add_column('KEY', key='key')
      table.add_column('VALUE', key='value')
      self._configure_table_columns()
      table.add_row('⌛', '', Text(msg, overflow='fold', no_wrap=False))

    self.call_after_refresh(_do)

  def _render_table(self, items: list[dict], reveal: bool):
    table = self.query_one('#secrets-table', DataTable)
    table.clear(columns=True)
    table.add_column('✎', key='changed')
    table.add_column('KEY', key='key')
    table.add_column('VALUE', key='value')
    self._configure_table_columns()

    self._row_index_by_key = {}
    self._current = {}
    if reveal:
      self._original = {}
      self._changed = set()
      self._deleted = set()
      self._cursor_key = None

    if not items:
      table.add_row('', '', Text('No secrets in this folder', overflow='fold', no_wrap=False))
      self._revealed = reveal
      self._update_hint(reveal=reveal, saved=None)
      return

    items_sorted = sorted(
      items,
      key=lambda x: (x.get('secretKey') or '').lower()
    )

    for s in items_sorted:
      k = (s.get('secretKey') or '').strip()
      v = s.get('secretValue')

      if reveal:
        value_str = '' if v is None else str(v)
        self._original[k] = value_str
        self._current[k] = value_str
      else:
        self._current[k] = ''
        value_str = '<hidden>'

      # row_key = secret key → удобно для edit/save
      value_cell = Text(value_str, overflow='fold', no_wrap=False)
      table.add_row('', k, value_cell, key=k)
      try:
        self._row_index_by_key[k] = table.row_count - 1
      except Exception:
        pass

    # (do not change anything else)

    self._revealed = reveal
    self._update_hint(reveal=reveal, saved=None)

  def _update_hint(self, reveal: bool, saved: tuple[int, int, int] | None):
    hint = self.query_one('#secrets-hint', Static)
    key_style = styles.get('key', 'black on gray')

    esc_key = key('Esc', style_override=key_style)
    e_key = key('e', style_override=key_style)
    s_key = key('s', style_override=key_style)
    x_key = key('x', style_override=key_style)
    enter_key = key('Enter', style_override=key_style, literal=True)
    a_key = key('a', style_override=key_style)
    b_key = key('b', style_override=key_style)

    if saved is not None:
      created, updated, deleted = saved
      parts = [
        f'[white]{created}[/] created',
        f'[white]{updated}[/] updated',
      ]
      if deleted:
        parts.append(f'[white]{deleted}[/] deleted')
      hint.update(
        f'{esc_key} close   '
        f'[dim]Saved:[/] ' + ', '.join(parts)
      )
      return

    if reveal:
      hint.update(
        f'{esc_key} close   '
        f'{enter_key} edit value   '
        f'{x_key} mark delete   '
        f'{a_key} add   '
        f'{b_key} bulk add   '
        f'{s_key} save'
      )
    else:
      hint.update(
        f'{esc_key} close   '
        f'{e_key} allow edit'
      )

  async def _load_secrets(self, reveal: bool):
    try:
      secrets = await get_secrets(
        self.workspace_id,
        self.env_slug,
        secret_path=self.folder_path,
        recursive=False,
        reveal=reveal
      )
    except Exception as e:
      logging.error(
        f'Failed to load secrets for {self.workspace_id}/{self.env_slug}{self.folder_path}: {e}'
      )
      table = self.query_one('#secrets-table', DataTable)
      table.clear(columns=True)
      table.add_column('✎', key='changed')
      table.add_column('KEY', key='key')
      table.add_column('VALUE', key='value')
      self._configure_table_columns()
      table.add_row('⚠️', '', Text('Failed to load secrets', overflow='fold', no_wrap=False))
      return

    items: list[dict] = secrets if isinstance(secrets, list) else []
    self.call_after_refresh(lambda: self._render_table(items, reveal=reveal))

  async def _save_changes(self, to_create: dict[str, str], to_update: dict[str, str], to_delete: list[str]):
    deleted = 0
    created = 0
    updated = 0

    try:
      if to_create:
        await create_secrets_bulk(
          self.workspace_id,
          self.env_slug,
          self.folder_path,
          to_create
        )
        created = len(to_create)

      if to_update:
        await update_secrets_bulk(
          self.workspace_id,
          self.env_slug,
          self.folder_path,
          to_update
        )
        updated = len(to_update)
      
      if to_delete:
        await delete_secrets_bulk(
          self.workspace_id,
          self.env_slug,
          self.folder_path,
          to_delete
        )
        deleted = len(to_delete)

    except Exception as e:
      logging.error(
        f'Failed to save secrets for {self.workspace_id}/{self.env_slug}{self.folder_path}: {e}'
      )
      table = self.query_one('#secrets-table', DataTable)
      table.clear(columns=True)
      table.add_column('✎', key='changed')
      table.add_column('KEY', key='key')
      table.add_column('VALUE', key='value')
      self._configure_table_columns()
      table.add_row('⚠️', '', Text('Failed to save secrets', overflow='fold', no_wrap=False))
      return

    # применяем сохранённое как новое "оригинальное"
    self._original = dict(self._current)
    self._revealed = True
    self._edit_enabled = True

    def _done():
      for k in list(self._deleted):
        self._current.pop(k, None)
      # перерисуем таблицу как revealed
      items = [{'secretKey': k, 'secretValue': v} for k, v in self._current.items()]
      self._render_table(items, reveal=True)
      self._changed = set()
      self._deleted = set()
      # ensure Ch markers cleared in current table
      try:
        table = self.query_one('#secrets-table', DataTable)
        for i in range(table.row_count):
          if hasattr(table, 'update_cell_at'):
            table.update_cell_at(i, 0, '')
      except Exception:
        pass
      self._update_hint(reveal=True, saved=(created, updated, deleted))

    self.call_after_refresh(_done)


class FolderCreateScreen(Screen):
  '''Экран создания папок в конкретном environment.'''

  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
    ('enter', 'create', 'Create'),
  ]

  def __init__(self, workspace_id: str, env_slug: str, env_label: str, base_path: str):
    super().__init__()
    self.workspace_id = workspace_id
    self.env_slug = env_slug
    self.env_label = env_label
    self.base_path = base_path

  def action_cancel(self):
    self.app.pop_screen()

  def action_create(self):
    app = self.app
    if not isinstance(app, InfictlApp):
      return

    input_widget = self.query_one('#fc-input', Input)
    raw = input_widget.value.strip()
    specs = self._parse_folder_specs(raw)
    if not specs:
      app.bell()
      return

    app.run_worker(
      app._create_folders(
        self.workspace_id,
        self.env_slug,
        specs
      ),
      exclusive=True
    )
    self.app.pop_screen()

  def _parse_folder_specs(self, raw: str) -> list[tuple[str, str]]:
    '''Парсинг путей, с поддержкой абсолютных и относительных.'''
    specs: list[tuple[str, str]] = []

    parts = raw.replace(',', ' ').split()
    for part in parts:
      s = part.strip()
      if not s:
        continue

      if s.startswith('/'):
        full = s
      else:
        base = self.base_path or '/'
        if not base.startswith('/'):
          base = '/' + base
        base = base.rstrip('/')
        full = base + '/' + s

      full = full.rstrip('/')
      if not full:
        continue

      prefix, _, last = full.rpartition('/')
      folder_name = last or '/'
      folder_path = prefix or '/'

      specs.append((folder_path, folder_name))

    return specs

  def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == 'fc-input':
      self.action_create()

  def compose(self):
    env_color = styles.get('env_name', 'cyan')
    enter_key = key('enter')
    esc_key = key('Esc')
    title = (
      f'Create folders in '
      f'[{env_color}]{self.env_label}[/]'
    )
    yield Static(title, id='fc-title')
    yield Static(
      'Enter folders (comma/space separated):',
      id='fc-help'
    )
    yield Input(
      placeholder='e.g. db, somefolder/test2 my/folder/structure, /test123',
      id='fc-input'
    )
    yield Static(
      f'Paths without "/" are relative to current node. '
      f'Absolute paths start with "/".\n'
      f'Press {enter_key} to create, {esc_key} to cancel.',
      id='fc-hint'
    )
    yield Footer()

  def on_mount(self) -> None:
    self.query_one('#fc-input', Input).focus()


class ConfirmDeleteFolderScreen(Screen):
  '''Экран подтверждения удаления папки.'''

  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
    ('n', 'cancel', 'No'),
    ('y', 'confirm', 'Yes'),
    ('enter', 'confirm', 'Yes'),
  ]

  def __init__(self, workspace_id: str, env_slug: str, folder_path: str):
    super().__init__()
    self.workspace_id = workspace_id
    self.env_slug = env_slug
    self.folder_path = folder_path

  def action_cancel(self):
    self.app.pop_screen()

  def action_confirm(self):
    app = self.app
    if isinstance(app, InfictlApp):
      app.run_worker(
        app._delete_folder(
          self.workspace_id,
          self.env_slug,
          self.folder_path
        ),
        exclusive=True
      )
    self.app.pop_screen()

  def compose(self):
    folder_color = styles.get('folder_name', 'bright_yellow')
    env_color = styles.get('env_name', 'cyan')
    yes_key = key('y')
    enter_key = key('enter')
    no_key = key('n')
    esc_key = key('Esc')

    relative = self.folder_path.lstrip('/') or '/'
    yield Static(
      'Are you sure you want to delete folder\n'
      f'[{folder_color}]{relative}/[/] '
      f'in [{env_color}]{self.env_slug}[/]?',
      id='df-title'
    )
    yield Static(
      f'Press {yes_key}/{enter_key} to confirm or '
      f'{no_key}/{esc_key} to cancel.',
      id='df-help'
    )
    yield Footer()


class ConfirmDeleteEnvironmentScreen(Screen):
  '''Экран подтверждения удаления environment.'''

  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
    ('n', 'cancel', 'Cancel'),
    ('y', 'confirm', 'Delete'),
    ('enter', 'confirm', 'Delete'),
  ]

  def __init__(
    self,
    workspace_id: str,
    env_id: str,
    env_name: str,
    env_slug: str
  ):
    super().__init__()
    self.workspace_id = workspace_id
    self.env_id = env_id
    self.env_name = env_name
    self.env_slug = env_slug

  def action_cancel(self):
    self.app.pop_screen()

  def action_confirm(self):
    app = self.app
    if isinstance(app, InfictlApp):
      app.run_worker(
        app._delete_environment(
          self.workspace_id,
          self.env_id
        ),
        exclusive=True
      )
    self.app.pop_screen()

  def compose(self):
    env_color = styles.get('env_name', 'cyan')
    slug_color = styles.get('env_slug', 'grey50')
    yes_key = key('y')
    enter_key = key('enter')
    no_key = key('n')
    esc_key = key('Esc')

    label = Text()
    label.append(self.env_name or self.env_slug or 'environment', style=env_color)
    if self.env_slug and self.env_slug != self.env_name:
      label.append(' ')
      label.append(f'({self.env_slug})', style=slug_color)

    text = Text()
    text.append('Are you sure you want to delete environment\n')
    text.append(label)
    text.append('?')

    yield Static(text, id='de-title')
    yield Static(
      f'Press {yes_key}/{enter_key} to confirm or '
      f'{no_key}/{esc_key} to cancel.',
      id='de-help'
    )
    yield Footer()


class NewEnvironmentScreen(Screen):
  '''Экран создания нового environment.'''

  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
    ('enter', 'create', 'Create'),
  ]

  def __init__(self, workspace_id: str, workspace_name: str):
    super().__init__()
    self.workspace_id = workspace_id
    self.workspace_name = workspace_name

  def action_cancel(self):
    self.app.pop_screen()

  def action_create(self):
    app = self.app
    if not isinstance(app, InfictlApp):
      return

    name_input = self.query_one('#ne-name', Input)
    slug_input = self.query_one('#ne-slug', Input)

    name = name_input.value.strip()
    slug = slug_input.value.strip()

    if not name or not slug:
      app.bell()
      return

    app.run_worker(
      app._create_environment(
        self.workspace_id,
        name,
        slug
      ),
      exclusive=True
    )
    self.app.pop_screen()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    name_input = self.query_one('#ne-name', Input)
    slug_input = self.query_one('#ne-slug', Input)

    if event.input.id == 'ne-name':
      if not slug_input.value.strip():
        slug_input.focus()
        return

    self.action_create()

  def compose(self):
    ws_color = styles.get('workspace_name', 'yellow')
    enter_key = key('enter')
    esc_key = key('Esc')

    yield Static(
      f'Create environment in [{ws_color}]{self.workspace_name}[/]',
      id='ne-title'
    )
    yield Static(
      'Name: human-readable name, displayed in UI',
      id='ne-name-label'
    )
    yield Input(
      placeholder='e.g. Development, Staging, Production',
      id='ne-name'
    )
    yield Static(
      'Slug: environment slug, used in pipelines',
      id='ne-slug-label'
    )
    yield Input(
      placeholder='e.g. dev, staging, prod',
      id='ne-slug'
    )
    yield Static(
      f'Press {enter_key} to create, {esc_key} to cancel.',
      id='ne-help'
    )
    yield Footer()

  def on_mount(self) -> None:
    self.query_one('#ne-name', Input).focus()


# --------- CopySecretsScreen: copy all secrets from one folder to another ---------
class CopySecretsScreen(Screen):
  """Copy all secrets from one folder to another.

  - Select destination folder in a tree.
  - r toggles recursive copy (include subfolders).
  - If destination already has secrets, show warning.
  - If there are key conflicts that would be overwritten, require explicit checkbox.
  """

  BINDINGS = [
    ('escape', 'cancel', 'Cancel'),
    ('r', 'toggle_recursive', 'Recursive'),
  ]

  def __init__(
    self,
    workspace_id: str,
    workspace_label: str,
    source_env_slug: str,
    source_path: str,
  ):
    super().__init__()
    self.workspace_id = workspace_id
    self.workspace_label = workspace_label
    self.source_env_slug = source_env_slug
    self.source_path = source_path or '/'

    self._dest_env_slug: str | None = None
    self._dest_path: str | None = None

    self._recursive: bool = False
    self._conflicts: int = 0
    self._dest_has_any: bool = False

  def compose(self):
    ws_color = styles.get('workspace_name', 'yellow')
    env_color = styles.get('env_name', 'cyan')
    folder_color = styles.get('folder_name', 'bright_yellow')

    esc_key = key('Esc')
    r_key = key('r')
    enter_key = key('Enter', literal=True)

    yield Static(
      f'Copy secrets: [{env_color}]{self.source_env_slug}[/] '
      f'[{folder_color}]{self.source_path}[/]\n'
      f'Workspace: [{ws_color}]{self.workspace_label}[/]',
      id='cs-title'
    )

    yield Static(
      f'Select destination folder in the tree below. {r_key} toggle recursive. {esc_key} cancel.\n'
      f'Use {enter_key} to expand/collapse.',
      id='cs-help'
    )

    yield Tree('Loading...', id='cs-tree')

    yield Checkbox('Recursive (copy subfolders too)', value=False, id='cs-recursive')

    yield Static('', id='cs-warning')

    yield Checkbox(
      'I understand that existing secrets with same keys will be overwritten',
      value=False,
      id='cs-overwrite'
    )

    with Horizontal(id='cs-buttons'):
      yield Button('Copy', id='cs-copy', variant='primary')
      yield Button('Cancel', id='cs-cancel')

    yield Footer()

  def on_mount(self) -> None:
    # Hide overwrite checkbox by default
    self.query_one('#cs-overwrite', Checkbox).display = False
    self._set_warning('')
    self._set_copy_enabled(False)
    self.run_worker(self._load_tree(), exclusive=True)

  def action_cancel(self):
    self.app.pop_screen()

  def action_toggle_recursive(self):
    self._recursive = not self._recursive
    cb = self.query_one('#cs-recursive', Checkbox)
    cb.value = self._recursive
    self.run_worker(self._analyze_destination(), exclusive=True)

  def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
    if event.checkbox.id == 'cs-recursive':
      self._recursive = bool(event.value)
      self.run_worker(self._analyze_destination(), exclusive=True)
      return

    if event.checkbox.id == 'cs-overwrite':
      self._set_copy_enabled(self._can_copy_now())
      return

  def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
    node = event.node
    data = node.data or {}
    if data.get('kind') == 'folder':
      self._dest_env_slug = data.get('env_slug')
      self._dest_path = data.get('path')
      self.run_worker(self._analyze_destination(), exclusive=True)
    else:
      self._dest_env_slug = None
      self._dest_path = None
      self._conflicts = 0
      self._dest_has_any = False
      self._set_warning('')
      self.query_one('#cs-overwrite', Checkbox).display = False
      self._set_copy_enabled(False)

  def on_button_pressed(self, event: Button.Pressed) -> None:
    bid = event.button.id
    if bid == 'cs-cancel':
      self.action_cancel()
      return

    if bid != 'cs-copy':
      return

    if not self._can_copy_now():
      self.app.bell()
      return

    # close the screen and run copy from the app
    self.app.pop_screen()

    app = self.app
    if isinstance(app, InfictlApp):
      dest_env = self._dest_env_slug or ''
      dest_path = self._dest_path or '/'
      overwrite_ok = self.query_one('#cs-overwrite', Checkbox).value
      recursive = self._recursive
      app.run_worker(
        app._copy_secrets_between_folders(
          self.workspace_id,
          self.source_env_slug,
          self.source_path,
          dest_env,
          dest_path,
          recursive,
          overwrite_ok,
        ),
        exclusive=True
      )

  async def _load_tree(self) -> None:
    tree = self.query_one('#cs-tree', Tree)

    app = self.app
    if not isinstance(app, InfictlApp):
      tree.root.label = 'App error'
      tree.root.data = {'kind': 'none'}
      return

    ws = app.workspaces_by_id.get(self.workspace_id)
    if not ws:
      tree.root.label = 'Workspace not found'
      tree.root.data = {'kind': 'none'}
      return

    ws_color = styles.get('workspace_name', 'yellow')
    env_name_color = styles.get('env_name', 'cyan')
    env_slug_color = styles.get('env_slug', 'grey50')
    error_color = styles.get('error', 'red')
    folder_color = styles.get('folder_name', 'bright_yellow')

    root_label = Text()
    root_label.append(ws.get('name') or 'workspace', style=ws_color)

    tree.root.label = root_label
    tree.root.data = {'kind': 'workspace', 'workspace_id': self.workspace_id}
    tree.root.remove_children()
    tree.root.expand()

    for env in ws.get('environments', []):
      env_slug = env.get('slug') or ''
      env_name = env.get('name') or env_slug or '?'
      env_id = env.get('id') or env_slug

      env_label = Text()
      env_label.append(env_name, style=env_name_color)
      if env_slug and env_slug != env_name:
        env_label.append(' ')
        env_label.append(f'({env_slug})', style=env_slug_color)

      env_node = tree.root.add(
        env_label,
        data={'kind': 'environment', 'slug': env_slug, 'name': env_name, 'id': env_id}
      )
      env_node.expand()

      if not env_slug:
        env_node.add(Text('No slug', style=error_color), data={'kind': 'info'})
        continue

      try:
        folders = await list_folders(self.workspace_id, env_slug)
        secrets = await get_secrets(
          self.workspace_id,
          env_slug,
          secret_path='/',
          recursive=True,
          reveal=False
        )
        counts = list_folders_secrets(folders, secrets)
      except Exception as e:
        logging.error(f'Failed to load folders for copy tree {self.workspace_id}/{env_slug}: {e}')
        env_node.add(Text('Failed to load folders', style=error_color), data={'kind': 'info'})
        continue

      if not counts:
        continue

      nodes: dict[str, Tree.Node] = {'/': env_node}

      for path in sorted(counts.keys()):
        if path == '/':
          continue

        segments = [seg for seg in path.lstrip('/').split('/') if seg]
        current_path = ''
        parent_node = env_node

        for segment in segments:
          current_path = (current_path + '/' + segment) if current_path else ('/' + segment)

          if current_path in nodes:
            parent_node = nodes[current_path]
            continue

          label = Text()
          label.append(f'{current_path.lstrip("/")}/', style=folder_color)

          node = parent_node.add(
            label,
            data={
              'kind': 'folder',
              'env_slug': env_slug,
              'path': current_path,
            }
          )
          nodes[current_path] = node
          parent_node = node

  async def _analyze_destination(self) -> None:
    self._conflicts = 0
    self._dest_has_any = False

    overwrite = self.query_one('#cs-overwrite', Checkbox)
    overwrite.value = False
    overwrite.display = False

    if not self._dest_env_slug or not self._dest_path:
      self._set_warning('')
      self._set_copy_enabled(False)
      return

    if self._dest_env_slug == self.source_env_slug and self._normalize_path(self._dest_path) == self._normalize_path(self.source_path):
      self._set_warning('[red]Destination is the same as source[/]')
      self._set_copy_enabled(False)
      return

    try:
      dest_items = await get_secrets(
        self.workspace_id,
        self._dest_env_slug,
        secret_path=self._dest_path,
        recursive=False,
        reveal=False
      )
      dest_keys = { (it.get('secretKey') or '').strip() for it in (dest_items or []) if isinstance(it, dict) }
      dest_keys.discard('')
      self._dest_has_any = len(dest_keys) > 0
    except Exception as e:
      logging.error(f'Failed to analyze destination secrets: {e}')
      self._set_warning('[red]Failed to analyze destination[/]')
      self._set_copy_enabled(False)
      return

    try:
      if not self._recursive:
        src_items = await get_secrets(
          self.workspace_id,
          self.source_env_slug,
          secret_path=self.source_path,
          recursive=False,
          reveal=False
        )
        src_keys = { (it.get('secretKey') or '').strip() for it in (src_items or []) if isinstance(it, dict) }
        src_keys.discard('')
        self._conflicts = len(src_keys & dest_keys)
      else:
        src_paths = await self._list_source_folder_paths()
        conflicts = 0
        for sp in src_paths:
          dp = self._map_dest_path(sp)
          if not dp:
            continue
          try:
            s_items = await get_secrets(
              self.workspace_id,
              self.source_env_slug,
              secret_path=sp,
              recursive=False,
              reveal=False
            )
            d_items = await get_secrets(
              self.workspace_id,
              self._dest_env_slug,
              secret_path=dp,
              recursive=False,
              reveal=False
            )
          except Exception:
            continue

          s_keys = { (it.get('secretKey') or '').strip() for it in (s_items or []) if isinstance(it, dict) }
          d_keys = { (it.get('secretKey') or '').strip() for it in (d_items or []) if isinstance(it, dict) }
          s_keys.discard('')
          d_keys.discard('')
          conflicts += len(s_keys & d_keys)

        self._conflicts = conflicts

    except Exception as e:
      logging.error(f'Failed to compute conflicts: {e}')
      self._set_warning('[red]Failed to compute conflicts[/]')
      self._set_copy_enabled(False)
      return

    warnings: list[str] = []
    if self._dest_has_any:
      warnings.append('[yellow]Destination already contains secrets[/]')

    if self._conflicts > 0:
      warnings.append(f'[yellow]{self._conflicts}[/] key(s) will be overwritten')
      overwrite.display = True
    else:
      overwrite.display = False

    self._set_warning(' • '.join(warnings))
    self._set_copy_enabled(self._can_copy_now())

  async def _list_source_folder_paths(self) -> list[str]:
    folders = await list_folders(self.workspace_id, self.source_env_slug)
    secrets = await get_secrets(
      self.workspace_id,
      self.source_env_slug,
      secret_path='/',
      recursive=True,
      reveal=False
    )
    counts = list_folders_secrets(folders, secrets)

    base = self._normalize_path(self.source_path)
    prefix = base.rstrip('/') + '/'

    paths: list[str] = []
    for p in counts.keys():
      if p == '/':
        continue
      np = self._normalize_path(p)
      if np == base or np.startswith(prefix):
        paths.append(np)

    if base not in paths:
      paths.append(base)

    return sorted(set(paths))

  def _map_dest_path(self, source_path: str) -> str | None:
    if not self._dest_path:
      return None

    src_base = self._normalize_path(self.source_path)
    sp = self._normalize_path(source_path)

    if sp == src_base:
      rel = ''
    elif sp.startswith(src_base.rstrip('/') + '/'):
      rel = sp[len(src_base):]
    else:
      return None

    dest_base = self._normalize_path(self._dest_path)
    combined = (dest_base.rstrip('/') + rel).rstrip('/')
    return self._normalize_path(combined or '/')

  def _normalize_path(self, p: str) -> str:
    s = (p or '/').strip()
    if not s.startswith('/'):
      s = '/' + s
    s = s.rstrip('/')
    return s or '/'

  def _can_copy_now(self) -> bool:
    if not self._dest_env_slug or not self._dest_path:
      return False

    if self._dest_env_slug == self.source_env_slug and self._normalize_path(self._dest_path) == self._normalize_path(self.source_path):
      return False

    if self._conflicts > 0:
      return bool(self.query_one('#cs-overwrite', Checkbox).value)

    return True

  def _set_warning(self, msg: str) -> None:
    warn = self.query_one('#cs-warning', Static)
    warn.update(msg or '')

  def _set_copy_enabled(self, enabled: bool) -> None:
    btn = self.query_one('#cs-copy', Button)
    btn.disabled = not bool(enabled)


class InfictlApp(App[None]):
  def _apply_bulk_new_secrets(self, pairs: list[tuple[str, str]]) -> None:
    """Apply multiple K=V pairs into the active SecretsScreen.

    - New keys are added and marked changed.
    - Existing keys are updated (and marked changed if different from original).
    - Keys marked for deletion are un-deleted.
    """

    def _retry(tries_left: int) -> None:
      screen = self.screen
      if not isinstance(screen, SecretsScreen):
        if tries_left > 0:
          self.set_timer(0.05, lambda: _retry(tries_left - 1))
        return

      any_change = False

      for k, v in pairs:
        prev = screen._current.get(k)
        screen._current[k] = v
        screen._deleted.discard(k)

        original_val = screen._original.get(k)
        if original_val is None:
          screen._changed.add(k)
          any_change = True
        else:
          if v != original_val:
            screen._changed.add(k)
            any_change = True
          else:
            screen._changed.discard(k)

        if prev is None or prev != v:
          any_change = True

      if not any_change:
        self.bell()

      def _apply_to_table() -> None:
        screen._rerender_from_state()
        screen._update_hint(reveal=screen._revealed, saved=None)

      try:
        screen.call_after_refresh(_apply_to_table)
      except Exception:
        _apply_to_table()

    _retry(tries_left=10)
  CSS = '''
  Screen {
    align-horizontal: center;
    align-vertical: middle;
  }

  WorkspaceList {
    width: 75%;
    height: 50%;
  }

  #status {
    padding: 1 2;
  }

  #tree {
    padding: 1 2;
  }

  #secrets-title {
    padding: 1 2 0 2;
  }

  #secrets-hint {
    padding: 0 2 1 2;
  }

  #secrets-table {
    width: 90%;
    height: 1fr;
    margin: 0 2 1 2;
  }

  #ne-title {
    padding: 1 2;
  }

  #ne-name-label {
    padding: 0 2 0 2;
  }

  #ne-slug-label {
    padding: 0 2 0 2;
  }

  #ne-name {
    width: 80%;
    margin: 0 2 1 2;
  }

  #ne-slug {
    width: 50%;
    margin: 0 2 1 2;
  }

  #ne-help {
    padding: 0 2 1 2;
  }

  #fc-title {
    padding: 1 2;
  }

  #fc-help {
    padding: 0 2 0 2;
  }

  #fc-input {
    width: 80%;
    margin: 0 2 0 2;
  }

  #fc-hint {
    padding: 0 2 1 2;
  }

  #df-title {
    padding: 1 2;
  }

  #df-help {
    padding: 0 2 1 2;
  }

  #de-title {
    padding: 1 2;
  }

  #de-help {
    padding: 0 2 1 2;
  }
  #ba-title {
    padding: 1 2 0 2;
  }

  #ba-text {
    width: 90%;
    height: 12;
    margin: 0 2 0 2;
  }

  #ba-hint {
    padding: 0 2 1 2;
  }

  #ba-buttons {
    width: 90%;
    margin: 0 2 1 2;
    height: auto;
  }
  
  #cs-title {
    padding: 1 2 0 2;
  }

  #cs-help {
    padding: 0 2 1 2;
  }

  #cs-tree {
    width: 90%;
    height: 1fr;
    margin: 0 2 1 2;
  }

  #cs-recursive {
    padding: 0 2 0 2;
  }

  #cs-warning {
    padding: 0 2 0 2;
  }

  #cs-overwrite {
    padding: 0 2 0 2;
  }

  #cs-buttons {
    width: 90%;
    margin: 0 2 1 2;
    height: auto;
  }
  '''

  BINDINGS = [
    ('u', 'use_workspace', 'Use workspace'),
    ('n', 'new_environment', 'New environment'),
    ('f', 'create_folders', 'Create folder(s)'),
    ('v', 'view_contents', 'View contents'),
    ('c', 'copy_secrets_to', 'Copy secrets to...'),
    ('x', 'delete_selected', 'Delete selected'),
    ('q', 'quit', 'Quit'),
  ]

  def __init__(self):
    super().__init__()
    self.current_workspace_id: str | None = None
    self.current_workspace_label: str | None = None
    self.workspaces_by_id: dict[str, dict] = {}

  def compose(self):
    yield Static('', id='status')
    yield Tree('No workspace selected', id='tree')
    yield Footer()

  def on_mount(self) -> None:
    self._update_status()
    self.refresh_bindings()

  def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
    """Курсор по дереву сдвинулся стрелками."""
    self.refresh_bindings()

  def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
    self.refresh_bindings()

  def _apply_secret_value_edit(self, key_name: str, value: str) -> None:
    """Apply an edited secret value back into the active SecretsScreen and refresh the table."""

    def _retry(tries_left: int) -> None:
      screen = self.screen
      if not isinstance(screen, SecretsScreen):
        if tries_left > 0:
          self.set_timer(0.05, lambda: _retry(tries_left - 1))
        return

      screen._current[key_name] = value
      screen._deleted.discard(key_name)

      original_val = screen._original.get(key_name)
      if original_val is None or value != original_val:
        screen._changed.add(key_name)
      else:
        screen._changed.discard(key_name)

      def _apply_to_table() -> None:
        screen._rerender_from_state()
        screen._update_hint(reveal=screen._revealed, saved=None)

      try:
        screen.call_after_refresh(_apply_to_table)
      except Exception:
        _apply_to_table()

    _retry(tries_left=10)


  def _apply_new_secret(self, key_name: str, value: str) -> None:
    """Apply a newly added secret into the active SecretsScreen and refresh UI."""

    def _retry(tries_left: int) -> None:
      screen = self.screen
      if not isinstance(screen, SecretsScreen):
        if tries_left > 0:
          self.set_timer(0.05, lambda: _retry(tries_left - 1))
        return

      if key_name in screen._current:
        self.bell()
        return

      screen._current[key_name] = value
      screen._deleted.discard(key_name)
      screen._changed.add(key_name)

      def _apply_to_table() -> None:
        screen._rerender_from_state()
        screen._update_hint(reveal=screen._revealed, saved=None)

      try:
        screen.call_after_refresh(_apply_to_table)
      except Exception:
        _apply_to_table()

    _retry(tries_left=10)

  def action_view_contents(self) -> None:
    if self.current_workspace_id is None:
      self.bell()
      return

    # Prevent stacking multiple SecretsScreen instances
    if isinstance(self.screen, SecretsScreen):
      self.bell()
      return

    tree = self.query_one('#tree', Tree)
    node = tree.cursor_node
    if node is None:
      self.bell()
      return

    data = node.data or {}
    kind = data.get('kind')

    if kind != 'folder':
      self.bell()
      return

    env_slug = data.get('env_slug')
    folder_path = data.get('path') or '/'

    if not env_slug:
      self.bell()
      return

    self.push_screen(
      SecretsScreen(
        self.current_workspace_id,
        env_slug,
        folder_path
      )
    )

  def action_copy_secrets_to(self) -> None:
    """Open CopySecretsScreen for the currently selected folder node."""

    if self.current_workspace_id is None:
      self.bell()
      return

    # Prevent stacking multiple CopySecretsScreen instances
    if isinstance(self.screen, CopySecretsScreen):
      self.bell()
      return

    tree = self.query_one('#tree', Tree)
    node = tree.cursor_node
    if node is None:
      self.bell()
      return

    data = node.data or {}
    if data.get('kind') != 'folder':
      self.bell()
      return

    env_slug = data.get('env_slug')
    folder_path = data.get('path') or '/'

    if not env_slug:
      self.bell()
      return

    self.push_screen(
      CopySecretsScreen(
        workspace_id=self.current_workspace_id,
        workspace_label=self.current_workspace_label or '',
        source_env_slug=env_slug,
        source_path=folder_path,
      )
    )

  def _update_status(self) -> None:
    status = self.query_one('#status', Static)
    ws_color = styles.get('workspace_name', 'yellow')

    ku = key('u')
    kn = key('n')
    kf = key('f')
    kx = key('x')

    if self.current_workspace_label:
      status.update(
        f'Current workspace: [{ws_color}]{self.current_workspace_label}[/]\n'
        f'Press {ku} to change workspace, '
        f'{kn} to create environment, '
        f'{kf} to create folders, '
        f'{key("c")} to copy secrets, '
        f'{kx} to delete selected'
      )
    else:
      status.update(
        f'No workspace selected to use\n'
        f'Press {ku} to choose workspace'
      )

  def action_use_workspace(self) -> None:
    self.push_screen(WorkspaceSelectScreen())

  def _get_tree_and_cursor(self):
    tree = self.query_one('#tree', Tree)
    node = tree.cursor_node
    return tree, node

  def _get_selected_env_data(self):
    '''Вернуть (env_slug, env_name, env_id, base_path) по текущему курсору.'''
    tree, node = self._get_tree_and_cursor()
    if node is None:
      return None

    data = node.data or {}
    kind = data.get('kind')

    if kind == 'environment':
      slug = data.get('slug')
      name = data.get('name')
      env_id = data.get('id')
      return (slug, name, env_id, '/')

    if kind == 'folder':
      slug = data.get('env_slug')
      name = data.get('env_name') or slug
      env_id = data.get('env_id')
      path = data.get('path') or '/'
      return (slug, name, env_id, path)

    return None

  def check_action(self, action: str, parameters: tuple[object, ...]):
    """Control which actions are enabled/visible based on current context."""

    # Always available
    if action in ('use_workspace', 'quit'):
      return True

    # If SecretsScreen is active: disable ONLY app-level actions.
    # Let SecretsScreen's own actions (save/edit/etc) work normally.
    if isinstance(self.screen, SecretsScreen):
      if action in (
        'new_environment',
        'create_folders',
        'view_contents',
        'delete_selected',
        'copy_secrets_to',
      ):
        return None
      return True

    # If no workspace selected yet, disable workspace-dependent actions
    if self.current_workspace_id is None:
      if action in ('new_environment', 'create_folders', 'delete_selected', 'view_contents', 'copy_secrets_to'):
        return None
      return True

    # Workspace is selected: some actions depend on tree cursor
    if action == 'new_environment':
      return True

    # For folder/environment-related actions, inspect current node
    try:
      tree = self.query_one('#tree', Tree)
      node = tree.cursor_node
      data = (node.data or {}) if node else {}
      kind = data.get('kind')
    except Exception:
      kind = None

    if action == 'create_folders':
      return True if kind in ('environment', 'folder') else None

    if action == 'delete_selected':
      return True if kind in ('environment', 'folder') else None

    if action == 'view_contents':
      return True if kind == 'folder' else None

    if action == 'copy_secrets_to':
      return True if kind == 'folder' else None

    return True

  def action_new_environment(self) -> None:
    if self.current_workspace_id is None:
      self.bell()
      status = self.query_one('#status', Static)
      ku = key('u')
      status.update(
        f'No workspace selected to {ku}se\n'
        f'Select workspace first with {ku}'
      )
      return

    ws = self.workspaces_by_id.get(self.current_workspace_id)
    if not ws:
      self.bell()
      return

    self.push_screen(NewEnvironmentScreen(ws['id'], ws['name']))

  def action_create_folders(self) -> None:
    if self.current_workspace_id is None:
      self.bell()
      status = self.query_one('#status', Static)
      ku = key('u')
      status.update(
        f'No workspace selected to {ku}se\n'
        f'Select workspace first with {ku}'
      )
      return

    env_data = self._get_selected_env_data()
    if env_data is None:
      self.bell()
      return

    env_slug, env_name, _env_id, base_path = env_data
    if not env_slug:
      self.bell()
      return

    label = env_name or env_slug
    if env_slug and env_slug != env_name:
      label = f'{env_name} ({env_slug})'

    self.push_screen(
      FolderCreateScreen(
        self.current_workspace_id,
        env_slug,
        label,
        base_path
      )
    )

  def action_delete_selected(self) -> None:
    if self.current_workspace_id is None:
      self.bell()
      return

    tree, node = self._get_tree_and_cursor()
    if node is None:
      self.bell()
      return

    data = node.data or {}
    kind = data.get('kind')

    if kind == 'folder':
      env_slug = data.get('env_slug')
      folder_path = data.get('path')
      if not env_slug or not folder_path:
        self.bell()
        return
      self.push_screen(
        ConfirmDeleteFolderScreen(
          self.current_workspace_id,
          env_slug,
          folder_path
        )
      )
    elif kind == 'environment':
      env_id = data.get('id') or data.get('slug')
      env_slug = data.get('slug') or ''
      env_name = data.get('name') or env_slug

      if not env_id:
        self.bell()
        return

      self.push_screen(
        ConfirmDeleteEnvironmentScreen(
          self.current_workspace_id,
          env_id,
          env_name,
          env_slug
        )
      )
    else:
      self.bell()
  
  def on_key(self, event) -> None:
    if event.key in ('up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown'):
      self.refresh_bindings()

  async def _copy_secrets_between_folders(
    self,
    workspace_id: str,
    source_env_slug: str,
    source_path: str,
    dest_env_slug: str,
    dest_path: str,
    recursive: bool,
    overwrite_ok: bool,
  ) -> None:
    def _norm(p: str) -> str:
      s = (p or '/').strip()
      if not s.startswith('/'):
        s = '/' + s
      s = s.rstrip('/')
      return s or '/'

    def _map_dest(src_base: str, src_p: str, dst_base: str) -> str | None:
      sb = _norm(src_base)
      sp = _norm(src_p)
      db = _norm(dst_base)

      if sp == sb:
        rel = ''
      elif sp.startswith(sb.rstrip('/') + '/'):
        rel = sp[len(sb):]
      else:
        return None

      return _norm((db.rstrip('/') + rel).rstrip('/') or '/')

    src_base = _norm(source_path)
    dst_base = _norm(dest_path)

    if not workspace_id or not source_env_slug or not dest_env_slug:
      logging.error('Copy secrets: missing workspace/env')
      return

    if source_env_slug == dest_env_slug and src_base == dst_base:
      logging.warning('Copy secrets: destination equals source')
      return

    # Build list of source paths to copy
    if not recursive:
      src_paths = [src_base]
    else:
      src_paths: list[str] = []
      try:
        folders = await list_folders(workspace_id, source_env_slug)
        secrets_all = await get_secrets(
          workspace_id,
          source_env_slug,
          secret_path='/',
          recursive=True,
          reveal=False
        )
        counts = list_folders_secrets(folders, secrets_all)

        prefix = src_base.rstrip('/') + '/'
        for p in counts.keys():
          np = _norm(p)
          if np == src_base or np.startswith(prefix):
            src_paths.append(np)

        if src_base not in src_paths:
          src_paths.append(src_base)

        src_paths = sorted(set(src_paths))
      except Exception as e:
        logging.error(f'Copy secrets: failed to list source paths: {e}')
        src_paths = [src_base]

      # Best-effort create destination folder structure
      try:
        for sp in src_paths:
          dp = _map_dest(src_base, sp, dst_base)
          if not dp or dp == '/':
            continue

          segments = [seg for seg in dp.lstrip('/').split('/') if seg]
          cur_parent = '/'
          for seg in segments:
            try:
              await create_folder(
                workspace_id=workspace_id,
                environment_slug=dest_env_slug,
                folder_name=seg,
                folder_path=cur_parent,
                folder_description=''
              )
            except Exception:
              pass
            cur_parent = _norm((cur_parent.rstrip('/') + '/' + seg).rstrip('/'))
      except Exception as e:
        logging.error(f'Copy secrets: failed to ensure destination folders: {e}')

    total_created = 0
    total_updated = 0
    total_skipped = 0

    for sp in src_paths:
      dp = _map_dest(src_base, sp, dst_base)
      if not dp:
        continue

      # Source WITH values
      try:
        src_items = await get_secrets(
          workspace_id,
          source_env_slug,
          secret_path=sp,
          recursive=False,
          reveal=True
        )
      except Exception as e:
        logging.error(f'Copy secrets: failed to load source {sp}: {e}')
        continue

      src_items = src_items if isinstance(src_items, list) else []
      src_map: dict[str, str] = {}
      for it in src_items:
        if not isinstance(it, dict):
          continue
        k = (it.get('secretKey') or '').strip()
        if not k:
          continue
        v = it.get('secretValue')
        src_map[k] = '' if v is None else str(v)

      if not src_map:
        continue

      # Destination keys only
      try:
        dst_items = await get_secrets(
          workspace_id,
          dest_env_slug,
          secret_path=dp,
          recursive=False,
          reveal=False
        )
      except Exception as e:
        logging.error(f'Copy secrets: failed to load destination {dp}: {e}')
        continue

      dst_items = dst_items if isinstance(dst_items, list) else []
      dst_keys = {
        (it.get('secretKey') or '').strip()
        for it in dst_items
        if isinstance(it, dict)
      }
      dst_keys.discard('')

      to_create: dict[str, str] = {}
      to_update: dict[str, str] = {}

      for k, v in src_map.items():
        if k in dst_keys:
          if overwrite_ok:
            to_update[k] = v
          else:
            total_skipped += 1
        else:
          to_create[k] = v

      try:
        if to_create:
          await create_secrets_bulk(workspace_id, dest_env_slug, dp, to_create)
          total_created += len(to_create)

        if to_update:
          await update_secrets_bulk(workspace_id, dest_env_slug, dp, to_update)
          total_updated += len(to_update)
      except Exception as e:
        logging.error(f'Copy secrets: failed to write to {dp}: {e}')
        continue

    await self._load_workspace_tree()

    # short status message (non-sticky, keeps it simple)
    def _status() -> None:
      status = self.query_one('#status', Static)
      msg = f'Copied: {total_created} created, {total_updated} updated'
      if total_skipped:
        msg += f', {total_skipped} skipped'
      status.update(msg)

    try:
      self.call_after_refresh(_status)
    except Exception:
      pass

  async def _load_workspace_tree(self) -> None:
    tree = self.query_one('#tree', Tree)

    if self.current_workspace_id is None:
      tree.root.label = 'No workspace selected'
      tree.root.data = {'kind': 'none'}
      tree.root.remove_children()
      return

    ws = self.workspaces_by_id.get(self.current_workspace_id)
    if not ws:
      err_color = styles.get('error', 'red')
      tree.root.label = f'[{err_color}]Workspace data not found[/]'
      tree.root.data = {'kind': 'none'}
      tree.root.remove_children()
      return

    ws_color = styles.get('workspace_name', 'yellow')
    env_name_color = styles.get('env_name', 'cyan')
    env_slug_color = styles.get('env_slug', 'grey50')
    info_color = styles.get('info', 'grey50')
    error_color = styles.get('error', 'red')
    folder_color = styles.get('folder_name', 'bright_yellow')
    folder_count_color = styles.get('folder_count', 'white')
    folder_empty_color = styles.get('folder_empty', 'dim')
    folder_subfolders_color = styles.get(
      'folder_subfolders',
      folder_count_color
    )

    root_label = Text()
    root_label.append(ws['name'], style=ws_color)

    tree.root.label = root_label
    tree.root.data = {
      'kind': 'workspace',
      'workspace_id': ws['id'],
    }
    tree.root.remove_children()
    tree.root.expand()

    environments = ws.get('environments', [])

    for env in environments:
      env_slug = env.get('slug') or ''
      env_name = env.get('name') or env_slug or '?'
      env_id = env.get('id') or env_slug

      env_label = Text()
      env_label.append(env_name, style=env_name_color)
      if env_slug and env_slug != env_name:
        env_label.append(' ')
        env_label.append(f'({env_slug})', style=env_slug_color)

      env_node = tree.root.add(
        env_label,
        data={
          'kind': 'environment',
          'slug': env_slug,
          'name': env_name,
          'id': env_id,
        }
      )
      env_node.expand()

      if not env_slug:
        env_node.add(
          Text('No slug, cannot load data', style=error_color),
          data={'kind': 'info'}
        )
        continue

      try:
        folders = await list_folders(ws['id'], env_slug)
        secrets = await get_secrets(
          ws['id'],
          env_slug,
          secret_path='/',
          recursive=True,
          reveal=False
        )
        counts = list_folders_secrets(folders, secrets)
      except Exception as e:
        logging.error(
          f'Failed to load folders/secrets for {ws["id"]}/{env_slug}: {e}'
        )
        env_node.add(
          Text('Failed to load data', style=error_color),
          data={'kind': 'info'}
        )
        continue

      if not counts:
        env_node.add(
          Text('No folders', style=info_color),
          data={'kind': 'info'}
        )
        continue

      # --------- считаем количество подпапок (рекурсивно) ---------
      paths = [p for p in counts.keys() if p != '/']
      subfolder_counts: dict[str, int] = {}

      for path in paths:
        # для пути "/app" считаем все, кто начинается с "/app/"
        prefix = path.rstrip('/')
        if not prefix:
          continue
        prefix_with = prefix + '/'

        sub_count = 0
        for other in paths:
          if other != path and other.startswith(prefix_with):
            sub_count += 1
        subfolder_counts[path] = sub_count
      # -----------------------------------------------------------

      nodes: dict[str, Tree.Node] = {'/': env_node}

      for path in sorted(counts.keys()):
        if path == '/':
          continue

        count = counts.get(path, 0)
        segments = [seg for seg in path.lstrip('/').split('/') if seg]
        if not segments:
          continue

        current_path = ''
        parent_node = env_node

        for segment in segments:
          if current_path:
            current_path = current_path + '/' + segment
          else:
            current_path = '/' + segment

          if current_path in nodes:
            parent_node = nodes[current_path]
            continue

          folder_label_path = current_path.lstrip('/')
          folder_label = folder_label_path or '/'

          count_here = counts.get(current_path, 0)
          subfolders_here = subfolder_counts.get(current_path, 0)

          label = Text()
          label.append(f'{folder_label}/', style=folder_color)
          label.append('  ')

          # secrets / empty
          if count_here > 0:
            label.append(str(count_here), style=folder_count_color)
            label.append(' ')
            label.append('secrets', style=folder_empty_color)
          else:
            label.append('empty', style=folder_empty_color)

          # ", N subfolders" если есть подпапки
          if subfolders_here > 0:
            label.append(', ')
            label.append(str(subfolders_here), style=folder_subfolders_color)
            label.append(' ')
            label.append('subfolders', style=folder_empty_color)

          node = parent_node.add(
            label,
            data={
              'kind': 'folder',
              'env_slug': env_slug,
              'env_name': env_name,
              'env_id': env_id,
              'path': current_path,
              'count': count_here,
              'subfolders': subfolders_here,
            }
          )
          nodes[current_path] = node
          parent_node = node

  async def _create_folders(
    self,
    workspace_id: str,
    environment_slug: str,
    specs: list[tuple[str, str]]
  ) -> None:
    logging.info(
      f'Creating folders in {workspace_id}/{environment_slug}: {specs}'
    )

    for folder_path, folder_name in specs:
      try:
        result = await create_folder(
          workspace_id=workspace_id,
          environment_slug=environment_slug,
          folder_name=folder_name,
          folder_path=folder_path,
          folder_description=''
        )
        logging.debug(f'Created folder result: {result}')
      except Exception as e:
        logging.error(
          f'Error creating folder {folder_path}/{folder_name} '
          f'in {workspace_id}/{environment_slug}: {e}'
        )

    await self._load_workspace_tree()

  async def _delete_folder(
    self,
    workspace_id: str,
    environment_slug: str,
    folder_path: str
  ) -> None:
    stripped = folder_path.rstrip('/') or '/'
    if stripped == '/':
      logging.warning('Refusing to delete root folder "/"')
      return

    prefix, _, last = stripped.rpartition('/')
    folder_name = last or '/'
    folder_parent = prefix or '/'

    logging.info(
      f'Deleting folder {folder_parent}/{folder_name} '
      f'in {workspace_id}/{environment_slug}'
    )

    try:
      result = await delete_folder(
        workspace_id=workspace_id,
        environment_slug=environment_slug,
        folder_name=folder_name,
        folder_path=folder_parent
      )
      logging.debug(f'Deleted folder result: {result}')
    except Exception as e:
      logging.error(
        f'Error deleting folder {folder_parent}/{folder_name} '
        f'in {workspace_id}/{environment_slug}: {e}'
      )

    await self._load_workspace_tree()

  async def _delete_environment(
    self,
    workspace_id: str,
    environment_id: str
  ) -> None:
    logging.info(
      f'Deleting environment {environment_id} in workspace {workspace_id}'
    )

    try:
      result = await delete_environment(
        workspace_id=workspace_id,
        environment_id=environment_id
      )
      logging.debug(f'Deleted environment result: {result}')
    except Exception as e:
      logging.error(
        f'Error deleting environment {environment_id} in {workspace_id}: {e}'
      )
      return

    ws = self.workspaces_by_id.get(workspace_id)
    if ws is not None:
      envs = ws.get('environments', [])
      new_envs = []
      for env in envs:
        eid = env.get('id') or env.get('slug')
        if eid != environment_id:
          new_envs.append(env)
      ws['environments'] = new_envs

    await self._load_workspace_tree()

  async def _create_environment(
    self,
    workspace_id: str,
    environment_name: str,
    environment_slug: str
  ) -> None:
    logging.info(
      f'Creating environment {environment_name} ({environment_slug}) '
      f'in workspace {workspace_id}'
    )

    try:
      result = await create_environment(
        workspace_id=workspace_id,
        environment_name=environment_name,
        environment_slug=environment_slug
      )
      logging.debug(f'Created environment result: {result}')
    except Exception as e:
      logging.error(
        f'Error creating environment {environment_name} ({environment_slug}) '
        f'in {workspace_id}: {e}'
      )
      return

    ws = self.workspaces_by_id.get(workspace_id)
    if ws is not None:
      envs = ws.setdefault('environments', [])
      if isinstance(result, dict):
        new_env = {
          'name': result.get('name', environment_name),
          'slug': result.get('slug', environment_slug),
          'id': result.get('id') or result.get('slug', environment_slug),
        }
      else:
        new_env = {
          'name': environment_name,
          'slug': environment_slug,
          'id': environment_slug,
        }
      envs.append(new_env)

    await self._load_workspace_tree()


  def on_option_list_option_selected(
    self,
    event: OptionList.OptionSelected
  ) -> None:
    if isinstance(self.screen, WorkspaceSelectScreen):
      option = event.option
      self.current_workspace_id = option.id
      self.current_workspace_label = option.prompt.plain

      logging.info(
        f'Selected workspace: {self.current_workspace_id} '
        f'({self.current_workspace_label})'
      )

      self._update_status()
      self.refresh_bindings()
      self.run_worker(self._load_workspace_tree(), exclusive=True)
      self.pop_screen()



if __name__ == '__main__':
  app = InfictlApp()
  app.run()