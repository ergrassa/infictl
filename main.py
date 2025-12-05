import logging

from textual.app import App
from textual.widgets import Footer, OptionList
from textual import log

from app.api import get_workspaces


logging.basicConfig(
  level=logging.DEBUG,
  format='%(name)s - %(levelname)s - %(message)s'
)


class WorkspaceList(OptionList):
  async def on_mount(self) -> None:
    try:
      workspaces = await get_workspaces()
      for ws in workspaces:
        self.add_option(f"{ws['name']} ({ws['id']})")
    except Exception as e:
      log(f"Failed to load workspaces: {e}")
      self.add_option("⚠️ Failed to load workspaces")


class InfictlApp(App[None]):
  BINDINGS = [
    ("q", "quit", "Quit"),
  ]

  def compose(self):
    yield WorkspaceList()
    yield Footer()


if __name__ == '__main__':
  app = InfictlApp()
  app.run()
