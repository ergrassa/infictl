from textual.app import App
from textual.widgets import Label, Footer, OptionList

from app.api import get_workspaces


class WorkspaceList(OptionList):
  def compose(self):
    ws = await get_workspaces()
    for workspace in ws:
      yield Label(f"{workspace['name']} ({workspace['id']})")


class InfictlApp(App[None]):
  BINDINGS = [
    ("q", "quit", "Quit"),
  ]

  def compose(self):
    yield WorkspaceList()
    yield Footer()


if __name__ == "__main__":
  app = InfictlApp()
  app.run()
