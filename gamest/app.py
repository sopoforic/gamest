# pylint: disable=too-many-ancestors
"""Track time playing games."""
import datetime
import importlib
import logging
import os
import pkgutil
import platform
import sys
import traceback
import webbrowser
from collections import OrderedDict
from typing import Tuple, Union, Dict

from tkinter import (Tk, Frame, Toplevel, Label, Entry, Button, Checkbutton,
                     Text, StringVar, IntVar, E, W, DISABLED, NORMAL, END,
                     ttk, messagebox, filedialog, scrolledtext, PhotoImage)

import pkg_resources

import gamest_plugins
from .db import App, UserApp, PlaySession, Session, DBConfig
from .util import format_time
from . import plugins, DATA_DIR

if platform.system() == 'Windows':
    import ctypes

logger = logging.getLogger(__name__)


def excepthook(etype=None, value=None, tracebackobj=None):
    logger.critical(''.join(traceback.format_exception(
        etype=etype,
        value=value,
        tb=tracebackobj,
    )).strip())


sys.excepthook = excepthook


class FakeProcess:
    def __init__(self):
        self.running = True

    def is_running(self):
        return self.running


def generate_report():
    """Generate an HTML game report and return it as a string."""
    apps = list(Session.query(App).
                filter(App.user_apps.any(UserApp.play_sessions.any())).
                order_by(App.name).all())
    html = """
<!DOCTYPE html>
<head>
  <title>Gamest Report</title>
  <style type="text/css">
    td {{
      padding: 0 15px 0 15px;
      vertical-align: top;
    }}
    td pre {{
      margin: 0;
    }}
    table.details > tbody > tr:nth-child(even) {{
      background: #FFF;
    }}
    table.details > tbody > tr:nth-child(odd) {{
      background: #FAFAFF;
    }}
  </style>
</head>
<body>
  <section name="summaryTable">
    <h1>Summary</h1>
    {}
  </section>
  <section name="details">
    <h1>Details</h1>
    {}
  </section>
</body>
</html>
"""

    summary = """
<table>
  <thead>
    <tr>
      <th>Game</th>
      <th>Time played</th>
    </tr>
  </thead>
  <tbody>
"""
    for app in apps:
        summary += """\
    <tr>
      <td><a href=\"#{}\">{}</a></td>
      <td>{}</td>
    </tr>""".format(app.id, app.name, format_time(app.runtime))

    summary += "  </tbody>\n</table>\n"

    details = ""
    for app in apps:
        details += "<h2 id=\"{}\">{}</h2>\n".format(app.id, app.name)
        details += "<table class=\"details\">\n"
        details += "  <thead>\n"
        details += "    <tr>\n"
        details += "      <th>Started</th>\n"
        details += "      <th>Duration</th>\n"
        details += "      <th>Note</th>\n"
        details += "    </tr>\n"
        details += "  </thead>\n"
        details += "  <tbody>\n"
        for uapp in app.user_apps:
            if uapp.initial_runtime:
                details += "    <tr>\n"
                details += "      <td>Initial runtime</td>\n"
                details += "      <td>{}</td>\n".format(format_time(uapp.initial_runtime))
                details += "      <td></td>\n"
                details += "    </tr>\n"
            for session in uapp.play_sessions:
                details += "    <tr>\n"
                details += "      <td>{}</td>\n".format(
                    session.started.strftime('%Y-%m-%d %H:%M:%S'))
                details += "      <td>{}</td>\n".format(format_time(session.duration))
                note = session.note if session.note else ''
                if note and session.status_updates:
                    note += '<br><br>'
                if session.status_updates:
                    note += "        <table>\n"
                    note += "          <thead><tr><th>Timestamp</th><th>Update</th></tr></thead>\n"
                    note += "          <tbody>\n"
                    for update in session.status_updates:
                        note += "            <tr><td>{}</td><td><pre>{}</pre></td></tr>\n".format(
                            update.timestamp.strftime('%Y-%m-%d %H:%M:%S'), update.note)
                    note += "          </tbody></table>\n"
                details += "      <td>{}</td>\n".format(note)
                details += "    </tr>\n"
        details += "  </tbody>\n"
        details += "</table>\n"

    return html.format(summary, details)


class SearchableCombobox(ttk.Combobox):
    def __init__(self, parent, values):
        super().__init__(parent, values=values, state="readonly")
        self.values = values
        self.bind("<Key>", self.handle_keypress)
        self.focus_set()

    def handle_keypress(self, event):
        if event.char.isprintable():
            start = self.current() + 1 if self.current() != -1 else 0
            for index, game in enumerate(self.values[start:]):
                if game.upper().startswith(event.char.upper()):
                    self.current(index+start)
                    break
            else:
                for index, game in enumerate(self.values):
                    if game.upper().startswith(event.char.upper()):
                        self.current(index)


class AddBox(Frame):
    """Form for adding a new UserApp."""

    def __init__(self, parent, game='', identifier_plugin='', identifier_data='', title='', seconds='', notes=''):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)

        self.game = game

        self.plugin_entry = StringVar()
        self.plugin_entry.set(identifier_plugin)
        self.data_entry = StringVar()
        self.data_entry.set(identifier_data)
        self.title_entry = StringVar()
        self.title_entry.set(title)
        self.seconds_entry = StringVar()
        self.seconds_entry.set(seconds)
        self.notes_entry = StringVar()
        self.notes_entry.set(notes)

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = self.config.get('geometry', fallback='400x160')
        win.geometry(geometry)
        win.grid_columnconfigure(0, weight=0)
        win.grid_columnconfigure(1, weight=1)
        win.title("Add Game")

        self.games = [(g.id, g.name) for g in Session.query(App).order_by(App.name)]
        self.gamecombo = ttk.Combobox(win, values=[g[1] for g in self.games])
        if self.game:
            self.gamecombo.set(self.game)

        Label(win, text="Game: ").grid()
        self.gamecombo.grid(row=0, column=1, sticky=E+W)

        Label(win, text="Plugin: ").grid()
        Entry(win, textvariable=self.plugin_entry).grid(row=1, column=1, sticky=E+W)

        Label(win, text="Plugin Data: ").grid()
        Entry(win, textvariable=self.data_entry).grid(row=2, column=1, sticky=E+W)

        Label(win, text="Window Title: ").grid()
        Entry(win, textvariable=self.title_entry).grid(row=3, column=1, sticky=E+W)

        Label(win, text="Initial seconds: ").grid()
        Entry(win, textvariable=self.seconds_entry).grid(row=4, column=1, sticky=E+W)

        Label(win, text="Notes: ").grid()
        Entry(win, textvariable=self.notes_entry).grid(row=5, column=1, sticky=E+W)

        Button(win, text="Add Game", command=self.add_game).grid(row=6, columnspan=2)

        win.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.destroy()

    def add_game(self):
        try:
            user_app = UserApp()
            index = self.gamecombo.current()
            if index == -1:
                user_app.app = App(name=self.gamecombo.get())
                logger.info("Adding new app: %s", user_app.app.name)
            else:
                user_app.app_id = self.games[index][0]
            user_app.identifier_plugin = self.plugin_entry.get()
            user_app.identifier_data = self.data_entry.get()
            notes = self.notes_entry.get()
            user_app.notes = notes if notes else None
            seconds = self.seconds_entry.get()
            user_app.initial_runtime = int(seconds) if seconds else 0
            title = self.title_entry.get()
            user_app.window_text = title if title else None
            Session.add(user_app)
            Session.commit()
            logger.info("Added new userapp: %s", repr(user_app))

            for p in appli.persistent_plugins:
                if isinstance(p, plugins.IdentifierPlugin):
                    p.clear_cache()
        except Exception:
            Session.rollback()
        finally:
            self.on_closing()


class AddTimeBox(Frame):
    """Form for adding manual time to a game."""

    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)

        self.seconds_entry = StringVar()

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = self.config.get('geometry', fallback='400x120')
        win.geometry(geometry)
        win.protocol("WM_DELETE_WINDOW", self.on_closing)
        win.grid_columnconfigure(0, weight=0)
        win.grid_columnconfigure(1, weight=1)
        win.title("Add Time")

        self.games = [(g.id, g.name) for g in Session.query(App).order_by(App.name)]
        self.gamecombo = SearchableCombobox(win, values=[g[1] for g in self.games])

        Label(win, text="Game: ").grid()
        self.gamecombo.grid(row=0, column=1, sticky=E+W)

        Label(win, text="Added seconds: ").grid()
        Entry(win, textvariable=self.seconds_entry).grid(row=1, column=1, sticky=E+W)

        Button(win, text="Add Time", command=self.add_time).grid(row=2, columnspan=2)

    def on_closing(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.destroy()

    def add_time(self):
        try:
            user_app = None
            index = self.gamecombo.current()
            if index == -1:
                messagebox.showerror(
                    "No game selected",
                    "A game must be selected.")
            else:
                app = Session.query(App).get(self.games[index][0])

                user_app = Session.query(UserApp).filter(
                    UserApp.app == app,
                    UserApp.path == None,  # noqa: E711 pylint: disable=C0121
                    UserApp.window_text == None).first()  # noqa: E711 pylint: disable=C0121
                if not user_app:
                    user_app = UserApp(
                        app=app,
                        path=None,
                        window_text=None,
                        note=None,
                        initial_runtime=0)

                seconds = self.seconds_entry.get()
                user_app.initial_runtime += int(seconds) if seconds else 0

                Session.add(user_app)
                Session.commit()
                logger.info("Added manual time for userapp: %s", repr(user_app))
        except Exception:
            logger.exception("Failed to add manual time. UserApp: %r", user_app)
            Session.rollback()
        finally:
            self.on_closing()


class ManualSessionSelector(Frame):
    """Window to choose a game for a manual session."""

    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = self.config.get('geometry', fallback='400x80')
        win.geometry(geometry)
        win.protocol("WM_DELETE_WINDOW", self.on_closing)
        win.grid_columnconfigure(0, weight=0)
        win.grid_columnconfigure(1, weight=1)
        win.title("Start Manual Session")

        self.games = [(g.id, g.name) for g in Session.query(App).order_by(App.name)]
        self.gamecombo = SearchableCombobox(win, values=[g[1] for g in self.games])

        Label(win, text="Game: ").grid()
        self.gamecombo.grid(row=0, column=1, sticky=E+W)

        Button(win, text="Begin Session", command=self.begin_session).grid(row=5, columnspan=2)

    def on_closing(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.destroy()

    def begin_session(self):
        try:
            if not self.parent.RUNNING:
                index = self.gamecombo.current()
                if index == -1:
                    messagebox.showerror(
                        "No game selected",
                        "A game must be selected.")
                else:
                    app = Session.query(App).get(self.games[index][0])
                    uapp = Session.query(UserApp).filter(
                        UserApp.app == app,
                        UserApp.path == None,  # noqa pylint: disable=C0121
                        UserApp.window_text == None).first()  # noqa pylint: disable=C0121
                    if not uapp:
                        uapp = UserApp(app=app, path=None, window_text=None, note=None)
                        logger.info("Added new userapp: %s", repr(uapp))
                        Session.add(uapp)
                    ManualSession(self.parent, uapp)
            else:
                messagebox.showerror(
                    "Gaming session in progress",
                    "Another game is already running. Quit that game first.")
        except Exception:
            logger.exception("Exception in begin_session.")
            Session.rollback()
        finally:
            self.on_closing()


class ManualSession(Frame):
    """Window to indicate a running manual session."""

    def __init__(self, parent, user_app):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)
        self.user_app = user_app
        self.proc = FakeProcess()
        appli.RUNNING = (self.proc, self.user_app)
        self.createWidgets()

        self.win.protocol("WM_DELETE_WINDOW", self.end_session)

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = self.config.get('geometry', fallback='400x80')
        win.geometry(geometry)
        win.title("Manual Session")

        Label(win, text="A session of {} is in progress.".format(self.user_app.app)).grid()
        Button(win, text="End Session", command=self.end_session).grid(row=1)

    def end_session(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.proc.running = False
        self.destroy()


class PickGame(Frame):
    """Window listing running processes to add to gamest."""

    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)

        self.pick_games_list = []
        for p in appli.persistent_plugins:
            if isinstance(p, plugins.IdentifierPlugin):
                logger.debug("Adding candidates from %r", p)
                self.pick_games_list.extend(p.candidates())
                logger.debug("Added candidates from %r", p)

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = self.config.get('geometry', fallback='400x80')
        win.geometry(geometry)
        win.protocol("WM_DELETE_WINDOW", self.on_closing)
        win.grid_columnconfigure(0, weight=0)
        win.grid_columnconfigure(1, weight=1)
        win.title("Pick a Game")
        Label(win, text="Game: ").grid()
        try:
            self.pickgamecombo = ttk.Combobox(
                win,
                values=["{} ({}: {})".format(
                    g.note.replace('"', ''),
                    g.identifier_plugin,
                    g.identifier_data)
                        for g in self.pick_games_list])
            self.pickgamecombo.grid(row=0, column=1, sticky=E+W)
        except Exception:
            import pprint
            logger.exception("Failed to create pickgamecombo. Games:\n%s",
                             pprint.pformat(self.pick_games_list))
            Label(win, text="Failed to create pickgamecombo.").\
                grid(row=0, column=1, sticky=E+W)

        Button(win, text="Add Game", command=self.do_pickgame).grid(row=1, columnspan=2)
        Label(win, text="To add a game manually, leave the box empty.").grid(row=2, columnspan=2)

    def on_closing(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.destroy()

    def do_pickgame(self):
        """Create an AddBox for the selected process."""
        index = self.pickgamecombo.current()
        if index != -1:
            game = self.pick_games_list[index]
            AddBox(
                self.parent,
                identifier_plugin=game.identifier_plugin,
                identifier_data=game.identifier_data,
                title=game.note)
        else:
            AddBox(self.parent)
        self.on_closing()


class SessionNote(Frame):
    """Window for editing the session note."""

    def __init__(self, parent, session):
        Frame.__init__(self, parent)
        self.parent = parent
        self.session = session
        self.config = DBConfig(self.__class__.__name__)

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = self.config.get('geometry', fallback='600x400')
        win.geometry(geometry)
        win.protocol("WM_DELETE_WINDOW", self.on_closing)
        win.title("Add note to play session")

        Label(win, text="{}, {}".format(
            self.session.user_app,
            self.session.started.strftime('%Y-%m-%d %H:%M:%S'))).pack()

        self.note_text = Text(win, width=72, height=22)
        if self.session.note:
            self.note_text.insert(END, self.session.note)
        self.note_text.pack()

        Button(win, text="Edit Note", command=self.edit_note).pack()

    def on_closing(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.destroy()

    def edit_note(self):
        try:
            Session.add(self.session)
            self.session.note = self.note_text.get(1.0, END)
            Session.commit()
        except Exception:
            logger.exception("Exception in edit_note")
        finally:
            self.on_closing()


class SettingsTab(Frame):
    """A tab grouping related settings."""

    def __init__(self, parent, settings_template):
        super().__init__(parent)
        self.parent = parent
        self.settings_template = settings_template
        self.new_values = {}

        self.createWidgets()

    def createWidgets(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        for index, (key, template) in enumerate(self.settings_template.items()):
            Label(self, text=template['name']).grid(row=index, column=0)
            if template['type'] == 'list':
                text = scrolledtext.ScrolledText(self, width=60, height=template.get('lines', 3), undo=True)
                if DBConfig.getlist(*key):
                    text.insert(END, "\n".join(DBConfig.getlist(*key)))
                elif template.get('default') is not None:
                    text.insert(END, "\n".join(template.get('default')))
                self.new_values[key] = lambda text=text: list(text.get(1.0, END).splitlines())
                text.grid(row=index, column=1)
            elif template['type'] == 'bool':
                var = IntVar()
                var.set(DBConfig.get(*key, type=int, fallback=template.get('default')) or False)
                checkbutton = Checkbutton(self, variable=var)
                self.new_values[key] = lambda var=var: str(var.get())
                checkbutton.grid(row=index, column=1, sticky=W)
            else:
                var = StringVar()
                var.set(DBConfig.get(*key, fallback=template.get('default')) or '')
                entry = Entry(self, textvariable=var)
                self.new_values[key] = var.get
                entry.grid(row=index, column=1, sticky=E+W)

            if template.get('hint'):
                Button(
                    self,
                    text="?",
                    command=lambda key=key, template=template, index=index: messagebox.showinfo(
                        "Help for '{}'".format(template['name']),
                        template['hint'])).grid(row=index, column=2, sticky=E)

    def validate_settings(self):
        """Validate settings and show errors if invalid."""
        valid = True
        for key in self.new_values:
            if self.settings_template[key].get('validate'):
                try:
                    if self.settings_template[key].get('validate')(self.new_values[key]()) is False:
                        valid = False
                        messagebox.showerror(
                            "Error in {}".format(self.settings_template[key]['name']),
                            "Invalid value for {}".format(self.settings_template[key]['name']))
                except ValueError as exc:
                    valid = False
                    messagebox.showerror(
                        "Error in {}".format(self.settings_template[key]['name']),
                        "Error in {}: {}".format(key[0], str(exc)))
        return valid

    def save_settings(self):
        """Validate settings and save to DB."""
        if self.validate_settings():
            for key in self.new_values:
                if self.settings_template[key]['type'] == 'list':
                    DBConfig.delete(*key)
                    for value in self.new_values[key]():
                        DBConfig.set(*key, value, append=True)
                else:
                    DBConfig.set(*key, self.new_values[key]())


class SettingsBox(Frame):
    """Settings box containing settings tabs."""

    def __init__(self, parent):
        try:
            super().__init__(parent)
            self.parent = parent
            self.config = DBConfig(self.__class__.__name__)

            self.win = Toplevel(self)
            self.win.title("Gamest Settings")
            geometry = self.config.get('geometry', fallback=None)
            if geometry:
                self.win.geometry(geometry)

            self.notebook = ttk.Notebook(self.win)

            try:
                tab = SettingsTab(self.win, parent.settings_template)
            except Exception:
                logger.exception("Failed to build Application settings tab.")

            self.notebook.add(tab, text='Application')

            for plugin in parent.installed_plugins.values():
                if plugin.plugin.get_settings_template():
                    try:
                        tab = SettingsTab(self.win, plugin.plugin.get_settings_template())
                        self.notebook.add(tab, text=plugin.plugin.SETTINGS_TAB_NAME)
                    except Exception:
                        logger.exception("Failed to add tab for plugin %r", plugin)

            self.notebook.grid()
            Button(self.win, text="Save", command=self.save_settings).grid(sticky=E+W)
            Button(self.win, text="Cancel", command=self.on_closing).grid(sticky=E+W)

            self.win.protocol("WM_DELETE_WINDOW", self.on_closing)

        except Exception:
            logger.exception("Failed to build settings box.")
            raise

    def on_closing(self):
        self.config.set('geometry', '+' + self.win.winfo_geometry().split('+', maxsplit=1)[1])
        self.destroy()

    def save_settings(self):
        try:
            valid = True
            for tab in self.notebook.tabs():
                if not self.nametowidget(tab).validate_settings():
                    valid = False
            if valid:
                for tab in self.notebook.tabs():
                    self.nametowidget(tab).save_settings()
                self.parent.event_generate("<<SettingsUpdated>>")
                self.on_closing()
        except Exception as exc:
            logger.exception("Failed to save settings.")
            messagebox.showerror(
                "Failed to save settings",
                ("Failed to save settings: {}\n"
                 "\n"
                 "More information may be available in the log.").format(str(exc)))
            self.on_closing()


class Application(Frame):
    """The main application which holds all state."""

    def __init__(self, master=None, installed_plugins=None):
        Frame.__init__(self, master)
        self.RUNNING = None
        self.play_session = None
        self.started = None
        self.config = DBConfig(owner='Application')

        self.installed_plugins = installed_plugins
        self.active_plugins = []
        self.session_plugins = [
            p.plugin
            for p in installed_plugins.values()
            if hasattr(p, 'plugin') and issubclass(p.plugin, plugins.GamestSessionPlugin)
        ]
        persistent_plugins = [
            p.plugin
            for p in installed_plugins.values()
            if hasattr(p, 'plugin') and issubclass(p.plugin, plugins.GamestPersistentPlugin)
        ]

        self.persistent_plugins = []
        for plugin in persistent_plugins:
            try:
                self.persistent_plugins.append(plugin(self))
                logger.debug("Plugin activated: %s", plugin.__name__)
            except Exception:
                logger.exception("Could not initialize plugin %r.", plugin)

        master.grid_columnconfigure(0, weight=1)

        self.createWidgets()

        def update_log_level(event):
            del event
            if self.config.getboolean('debug', fallback=False):
                logging.getLogger().setLevel(logging.DEBUG)
                logger.info("Log level set to DEBUG")
            else:
                logging.getLogger().setLevel(logging.INFO)
                logger.info("Log level set to INFO")

        self.bind("<<SettingsUpdated>>", update_log_level, "+")

    settings_template: Dict[Tuple[str, str], Dict[str, Union[str, bool]]] = OrderedDict()
    settings_template[('Application', 'confirm_exit')] = {
        'name': 'Confirm exit',
        'type': 'bool',
        'default': True,
        'hint': "If checked, gamest will ask for confirmation before exiting.",
    }
    settings_template[('Application', 'debug')] = {
        'name': 'Debug',
        'type': 'bool',
        'default': False,
        'hint': "Write additional debug messages to the log file.",
    }

    @staticmethod
    def do_report():
        """Create and save a playtime report."""
        filename = filedialog.asksaveasfilename(
            initialdir=DATA_DIR,
            initialfile='report.html',
            title="Save report as...",
            filetypes=(("HTML files", "*.html"),),
        )
        if filename:
            html = generate_report()
            with open(filename, 'wb') as outfile:
                outfile.write(html.encode('utf_8'))
            path = 'file://' + os.path.abspath(filename)
            webbrowser.open(path, new=2)

    def createWidgets(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.running_text = StringVar()
        self.running_text.set("Now running: ")
        self.rtlabel = Label(self, textvariable=self.running_text)
        self.rtlabel.grid(row=0, column=0)
        Label(self, text="Total runtime: ").grid(row=1, column=0)
        Label(self, text="This session: ").grid(row=2, column=0)

        self.running_app = StringVar()
        self.running_app.set("Nothing")
        self.running = Label(self, textvariable=self.running_app)
        self.running.grid(row=0, column=1)

        self.time_text = StringVar()
        self.time_text.set("N/A")
        Label(self, textvariable=self.time_text).grid(row=1, column=1)

        self.elapsed_text = StringVar()
        self.elapsed_text.set("N/A")
        Label(self, textvariable=self.elapsed_text).grid(row=2, column=1)

        Button(self, text="Add Game", command=lambda: PickGame(self)).grid(row=3, column=0)
        Button(self, text="Settings", command=lambda: SettingsBox(self)).grid(row=3, column=1)
        Button(self, text="Save report", command=self.do_report).grid(row=4, column=0)
        self.note_button = Button(
            self,
            text="Edit Note",
            command=lambda: SessionNote(self, self.play_session),
            state=DISABLED)
        self.note_button.grid(row=4, column=1)
        Button(
            self,
            text="Add Time",
            command=lambda: AddTimeBox(self)).grid(row=5, column=0)
        self.manual_session_button = Button(
            self,
            text="Begin Manual Session",
            command=lambda: ManualSessionSelector(self),
            state=NORMAL)
        self.manual_session_button.grid(row=5, column=1)

        self.grid(stick=E+W)

    def run(self):
        """Check for a new game every five seconds.

        This method runs when no game is currently being tracked.
        """
        try:
            for p in appli.persistent_plugins:
                if isinstance(p, plugins.IdentifierPlugin):
                    self.RUNNING = p.identify_game()
                    if self.RUNNING is not None:
                        break
            if self.RUNNING is not None:
                self.manual_session_button.config(state=DISABLED)
                self.rtlabel.config(fg='green')
                self.started = datetime.datetime.now()
                self.RUNNING = (self.RUNNING[0], Session.merge(self.RUNNING[1]))
                self.play_session = PlaySession(
                    user_app=self.RUNNING[1],
                    started=self.started)
                Session.add(self.play_session)
                Session.flush()
                for plugin in self.session_plugins:
                    try:
                        self.active_plugins.append(plugin(self))
                        logger.debug("Plugin activated: %s", plugin.__name__)
                    except plugins.UnsupportedAppError:
                        pass
                    except Exception:
                        logger.exception("Failed to initialize session plugin %r.", plugin)
                self.event_generate("<<GameStart{}>>".format(self.play_session.id))
                logger.debug("Now running %s", self.RUNNING[1].app.name)
                self.running_text.set("Now running: ")
                self.running_app.set(
                    "{} (#{})".format(
                        self.RUNNING[1].app.name,
                        self.RUNNING[1].id))
                self.time_text.set(
                    "{}".format(
                        format_time(self.RUNNING[1].app.runtime)))
                self.elapsed_text.set(format_time(0))
            if self.RUNNING is None:
                root.after(5000, self.run)
                self.manual_session_button.config(state=NORMAL)
            else:
                root.after(5000, self.wait)
        except Exception:
            logger.exception("Mysterious error")
            root.after(5000, self.run)
        finally:
            root.update()
            Session.commit()

    def wait(self):
        """Update running game state every 5 seconds.

        This method runs when a game is currently being tracked.
        """
        try:
            if self.RUNNING[0].is_running():
                try:
                    elapsed = int((datetime.datetime.now() - self.started).total_seconds())
                    self.play_session.duration = elapsed
                    self.note_button.config(state=NORMAL)
                    self.time_text.set(format_time(self.RUNNING[1].app.runtime))
                    self.elapsed_text.set(format_time(elapsed))
                except Exception:
                    logger.exception("Failure in running branch")
            else:
                self.RUNNING = None
                try:
                    self.rtlabel.config(fg='black')
                    elapsed = int((datetime.datetime.now() - self.started).total_seconds())
                    self.play_session.duration = elapsed
                    self.running_text.set("Last running: ")
                except Exception:
                    logger.exception("Failure in not running branch")
                finally:
                    self.manual_session_button.config(state=NORMAL)
                    self.event_generate("<<GameEnd{}>>".format(self.play_session.id))
                    self.active_plugins = []
                    self.unbind("<<GameStart{}>>".format(self.play_session.id))
                    self.unbind("<<GameEnd{}>>".format(self.play_session.id))
        except Exception:
            self.RUNNING = None
            logger.exception("Failure with is_running(), probably")
        finally:
            root.update()
            if self.RUNNING:
                root.after(5000, self.wait)
            else:
                root.after(5000, self.run)
            Session.commit()


def main():
    if DBConfig.getboolean('Application', 'debug', fallback=False):
        logging.getLogger().setLevel(logging.DEBUG)
    if platform.system() == 'Windows' and not ctypes.windll.shell32.IsUserAnAdmin():
        # restart as administrator
        sys.exit(
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                sys.argv[0],
                ' '.join(sys.argv[1:]), None, 1))

    try:
        logger.info("Starting gamest %s", pkg_resources.get_distribution('gamest').version)
    except pkg_resources.DistributionNotFound:
        logger.info("Starting gamest (version not available)")

    global root
    global appli
    root = Tk()
    root.wm_title("Gamest")
    geometry = DBConfig.get('Application', 'geometry', fallback='400x150')
    root.geometry(geometry)

    installed_plugins = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in pkgutil.iter_modules(gamest_plugins.__path__, gamest_plugins.__name__ + ".")
    }

    logger.debug("Plugins found: %s", list(installed_plugins.keys()))

    appli = Application(master=root, installed_plugins=installed_plugins)
    icon = PhotoImage("icon", file=pkg_resources.resource_filename('gamest', 'icon.png'))
    appli.tk.call('wm', 'iconphoto', root._w, icon)
    root.after(1000, appli.run)

    def on_closing():
        if (DBConfig.getboolean('Application', 'confirm_exit', fallback=True) is False or
                messagebox.askokcancel("Quit", "Do you want to quit?")):
            if appli.RUNNING is not None:
                logger.debug("appli.RUNNING is not None")
                try:
                    if appli.RUNNING[0].is_running():
                        elapsed = int((datetime.datetime.now() - appli.started).total_seconds())
                        appli.play_session.duration = elapsed
                        Session.commit()
                except Exception:
                    logger.exception("Failed is_running check on shutdown")
            for plugin in set().union(appli.persistent_plugins, appli.active_plugins):
                if hasattr(plugin, 'cleanup'):
                    try:
                        plugin.cleanup()
                    except NotImplementedError:
                        continue
                    except Exception:
                        logger.exception("Exception cleaning up %s", plugin.__class__.__name__)
            DBConfig.set('Application', 'geometry', root.winfo_geometry())
            logger.debug("Committing and quitting.")
            Session.commit()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    appli.mainloop()


if __name__ == '__main__':
    main()
