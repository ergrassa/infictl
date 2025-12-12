import logging

from rich.text import Text

from textual.app import App
from textual.screen import Screen
from textual.widgets import Footer, Static, OptionList, Input, Tree
from textual.widgets.option_list import Option

from app.api import (
  get_workspaces,
  get_secrets,
  create_folder,
  list_folders,
  delete_folder,
  create_environment,
  delete_environment,
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
    esc_key = key('esc')
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
    esc_key = key('esc')

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
    esc_key = key('esc')

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
    esc_key = key('esc')

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


class InfictlApp(App[None]):
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
  '''

  BINDINGS = [
    ('u', 'use_workspace', 'Use workspace'),
    ('n', 'new_environment', 'New environment'),
    ('f', 'create_folders', 'Create folder(s)'),
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
    """Enter по узлу — на всякий случай тоже обновляем."""
    self.refresh_bindings()

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
    # use_workspace and quit are always available
    if action in ('use_workspace', 'quit'):
      return True

    # If no workspace selected yet, disable workspace-dependent actions
    if self.current_workspace_id is None:
      if action in ('new_environment', 'create_folders', 'delete_selected'):
        # show in footer but as disabled
        return None
      return True

    # Workspace is selected: some actions depend on tree cursor
    if action == 'new_environment':
      # always allowed when workspace is selected
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
      # only when cursor is on environment or folder
      if kind in ('environment', 'folder'):
        return True
      return None

    if action == 'delete_selected':
      # only when cursor is on environment or folder
      if kind in ('environment', 'folder'):
        return True
      return None

    # default: enabled
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

  def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
    # Tree cursor changed, update available actions in the footer
    self.refresh_bindings()

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
