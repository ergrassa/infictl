import logging

from rich.text import Text

from textual.app import App
from textual.screen import Screen
from textual.widgets import Footer, Static, OptionList
from textual.widgets.option_list import Option

from app.api import get_workspaces


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
    # запускаем загрузку в фоне, чтобы UI сразу показал экран и "Loading"
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

      for ws in workspaces:
        text = Text()
        text.append(ws['name'], style='yellow')
        text.append(' ')
        text.append(f'({ws["slug"]})', style='grey50')

        option_list.add_option(Option(text, id=ws['id']))

    except Exception as e:
      logging.error(f'Failed to get workspaces: {e}')
      option_list.clear_options()
      option_list.add_option(
        Option('⚠️ Failed to load workspaces', disabled=True)
      )


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
  '''

  BINDINGS = [
    ('u', 'use_environment', 'Use environment'),
    ('q', 'quit', 'Quit'),
  ]

  def __init__(self):
    super().__init__()
    self.current_workspace_id: str | None = None
    self.current_workspace_label: str | None = None

  def compose(self):
    yield Static('', id='status')
    yield Footer()

  def on_mount(self) -> None:
    self._update_status()

  def _update_status(self) -> None:
    status = self.query_one('#status', Static)

    if self.current_workspace_label:
      status.update(
        f'Current workspace: [yellow]{self.current_workspace_label}[/yellow]\n'
        'Press [yellow]u[/yellow] to change'
      )
    else:
      status.update('No workspace selected to [yellow]u[/yellow]se')

  def action_use_environment(self) -> None:
    self.push_screen(WorkspaceSelectScreen())

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
      self.pop_screen()


if __name__ == '__main__':
  app = InfictlApp()
  app.run()
