import ctypes
import datetime
import importlib
import logging
import os
import pkg_resources
import pkgutil
import sys
import traceback
import webbrowser
from collections import OrderedDict
from tkinter import (Tk, Frame, Toplevel, Label, Entry, Button, Checkbutton,
    Text,
    StringVar, IntVar,
    N, S, E, W, DISABLED, NORMAL, END,
    ttk, messagebox, filedialog)

import psutil

import gamest_plugins
from .db import App, UserApp, PlaySession, Session, DBConfig
from .util import format_time
from . import plugins, DATA_DIR

logger = logging.getLogger(__name__)

def excepthook(excType=None, excValue=None, tracebackobj=None):
    logger.critical(''.join(traceback.format_exception(
        etype=excType,
        value=excValue,
        tb=tracebackobj,
    )).strip())

sys.excepthook = excepthook

class FakeProcess:
    def __init__(self):
        self.running = True

    def is_running(self):
        return self.running

def identify_window(pid, text):
    """Identify the app associated with a window."""
    proc = None
    path = None
    uas = Session.query(UserApp).filter(UserApp.window_text == text)
    nontext = Session.query(UserApp).filter(UserApp.window_text == None)
    if uas.count():
        proc = psutil.Process(pid)
        try:
            path = proc.exe()
        except psutil.AccessDenied:
            path = proc.name()
        logger.debug("Trying to identify app, path=%s", path)
        app = uas.filter(UserApp.path == path).first()
        if app:
            return app, proc
    if nontext.count():
        if proc == None:
            proc = psutil.Process(pid)
            path = proc.exe()
            app = nontext.filter(UserApp.path == path).first()
            if app:
                return app, proc
    return None, None

trash = ['Default IME',
         'MSCTFIME UI',
         'xonsh',
         'Battery Meter',
         'Network Flyout',
         'python',
         'Origin',
         'HiddenFaxWindow',
         'raptr',
         'Steam',
         'Settings',
         'Dropbox',
         'Program Manager',
         'Gamest'
         ]

EnumWindows = ctypes.windll.user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
GetWindowText = ctypes.windll.user32.GetWindowTextW
GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId

seen = set()

def foreach_window(hwnd, lParam):
    pid = ctypes.c_ulong()
    length = GetWindowTextLength(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    GetWindowText(hwnd, buff, length + 1)
    GetWindowThreadProcessId(hwnd, ctypes.pointer(pid))
    if not buff.value or buff.value in trash:
        return True
    if (pid.value, buff.value) in seen:
        return True
    try:
        app, proc = identify_window(pid.value, buff.value)
    except psutil.AccessDenied:
        seen.add((pid.value, buff.value))
        return True
    if app:
        logger.debug("Identified app: %s", app.app.name)
        appli.RUNNING = (proc, app)
        return False
    else:
        seen.add((pid.value, buff.value))
        return True

def generate_report():
    apps = list(Session.query(App).filter(App.user_apps.any(UserApp.play_sessions.any())).order_by(App.name).all())
    html = (
"""
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
)
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
    for a in apps:
        summary += "    <tr>\n"
        summary += "      <td><a href=\"#{}\">{}</a></td>\n".format(a.id, a.name)
        summary += "      <td>{}</td>\n".format(format_time(a.runtime))
        summary += "    </tr>\n"
    summary += "  </tbody>\n</table>\n"

    details = ""

    for a in apps:
        details += "<h2 id=\"{}\">{}</h2>\n".format(a.id, a.name)
        details += "<table class=\"details\">\n"
        details += "  <thead>\n"
        details += "    <tr>\n"
        details += "      <th>Started</th>\n"
        details += "      <th>Duration</th>\n"
        details += "      <th>Note</th>\n"
        details += "    </tr>\n"
        details += "  </thead>\n"
        details += "  <tbody>\n"
        for u in a.user_apps:
            if u.initial_runtime:
                details += "    <tr>\n"
                details += "      <td>Initial runtime</td>\n"
                details += "      <td>{}</td>\n".format(format_time(u.initial_runtime))
                details += "      <td></td>\n"
                details += "    </tr>\n"
            for s in u.play_sessions:
                details += "    <tr>\n"
                details += "      <td>{}</td>\n".format(s.started.strftime('%Y-%m-%d %H:%M:%S'))
                details += "      <td>{}</td>\n".format(format_time(s.duration))
                note = s.note if s.note else ''
                if note and s.status_updates:
                    note += '<br><br>'
                if s.status_updates:
                    note += "        <table>\n"
                    note += "          <thead><tr><th>Timestamp</th><th>Update</th></tr></thead>\n"
                    note += "          <tbody>\n"
                    for update in s.status_updates:
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
    def __init__(self, parent, game='', path='', title='', seconds='', notes=''):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)

        self.game = game

        self.path_entry = StringVar()
        self.path_entry.set(path)
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

        Label(win, text="Path: ").grid()
        Entry(win, textvariable=self.path_entry).grid(row=1, column=1, sticky=E+W)

        Label(win, text="Window Title: ").grid()
        Entry(win, textvariable=self.title_entry).grid(row=2, column=1, sticky=E+W)

        Label(win, text="Initial seconds: ").grid()
        Entry(win, textvariable=self.seconds_entry).grid(row=3, column=1, sticky=E+W)

        Label(win, text="Notes: ").grid()
        Entry(win, textvariable=self.notes_entry).grid(row=4, column=1, sticky=E+W)

        Button(win, text="Add Game", command=self.add_game).grid(row=5, columnspan=2)

        win.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.destroy()

    def add_game(self):
        try:
            ua = UserApp()
            index = self.gamecombo.current()
            if index == -1:
                ua.app = App(name=self.gamecombo.get())
                logger.info("Adding new app: %s", ua.app.name)
            else:
                ua.app_id = self.games[index][0]
            ua.path = self.path_entry.get()
            notes = self.notes_entry.get()
            ua.notes = notes if notes else None
            seconds = self.seconds_entry.get()
            ua.initial_runtime = int(seconds) if seconds else 0
            title = self.title_entry.get()
            ua.window_text = title if title else None
            Session.add(ua)
            Session.commit()
            logger.info("Added new userapp: %s", repr(ua))

            # reset the seen items so the new app can be detected
            global seen
            seen = set()
        except Exception:
            Session.rollback()
        finally:
            self.on_closing()

class AddTimeBox(Frame):
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
            ua = UserApp()
            index = self.gamecombo.current()
            if index == -1:
                messagebox.showerror(
                    "No game selected",
                    "A game must be selected.")
            else:
                app = Session.query(App).get(self.games[index][0])

                ua = Session.query(UserApp).filter(
                    UserApp.app == app,
                    UserApp.path == None,
                    UserApp.window_text == None).first()
                if not ua:
                    ua = UserApp(app=app, path=None, window_text=None, note=None, initial_runtime=0)

                seconds = self.seconds_entry.get()
                ua.initial_runtime += int(seconds) if seconds else 0

                Session.add(ua)
                Session.commit()
                logger.info("Added manual time for userapp: %s", repr(ua))
        except Exception:
            logger.exception("Failed to add manual time. UserApp: %r", ua)
            Session.rollback()
        finally:
            self.on_closing()

class ManualSessionSelector(Frame):
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
                    ua = Session.query(UserApp).filter(
                        UserApp.app == app,
                        UserApp.path == None,
                        UserApp.window_text == None).first()
                    if not ua:
                        ua = UserApp(app=app, path=None, window_text=None, note=None)
                        logger.info("Added new userapp: %s", repr(ua))
                        Session.add(ua)
                    ManualSession(self.parent, ua)
            else:
                messagebox.showerror(
                    "Gaming session in progress",
                    "Another game is already running. Quit that game first.")
        except:
            logger.exception("Exception in begin_session.")
            Session.rollback()
        finally:
            self.on_closing()

class ManualSession(Frame):
    def __init__(self, parent, ua):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)
        self.ua = ua
        self.proc = FakeProcess()
        appli.RUNNING = (self.proc, self.ua)
        self.createWidgets()

        self.win.protocol("WM_DELETE_WINDOW", self.end_session)

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = self.config.get('geometry', fallback='400x80')
        win.geometry(geometry)
        win.title("Manual Session")

        Label(win, text="A session of {} is in progress.".format(self.ua.app)).grid()
        Button(win, text="End Session", command=self.end_session).grid(row=1)

    def end_session(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.proc.running = False
        self.destroy()

class PickGame(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent
        self.config = DBConfig(self.__class__.__name__)

        self.pick_games_list = []
        EnumWindows(EnumWindowsProc(self.populate_games), 1)

        self.createWidgets()

    def populate_games(self, hwnd, lParam):
        pid = ctypes.c_ulong()
        length = GetWindowTextLength(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        GetWindowThreadProcessId(hwnd, ctypes.pointer(pid))
        if self.config.getboolean('visible_only', fallback=True) and (not buff.value or buff.value in trash or not ctypes.windll.user32.IsWindowVisible(hwnd)):
            return True
        try:
            proc = psutil.Process(pid.value)
            try:
                path = proc.exe()
            except psutil.AccessDenied:
                path = proc.name()
            self.pick_games_list.append((buff.value, path))
        except:
            pass
        return True

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
            self.pickgamecombo = ttk.Combobox(win, values=["{} ({})".format(g[0].replace('"', ''), g[1]) for g in self.pick_games_list])
            self.pickgamecombo.grid(row=0, column=1, sticky=E+W)
        except:
            import pprint
            logger.exception("Failed to create pickgamecombo. Games:\n%s\n\nException follows.", pprint.pformat(self.pick_games_list))
            Label(win, text="Failed to create pickgamecombo.").grid(row=0, column=1, sticky=E+W)

        Button(win, text="Add Game", command=self.do_pickgame).grid(row=1, columnspan=2)
        Label(win, text="To add a game manually, leave the box empty.").grid(row=2, columnspan=2)

    def on_closing(self):
        self.config.set('geometry', self.win.winfo_geometry())
        self.destroy()

    def do_pickgame(self):
        index = self.pickgamecombo.current()
        if index != -1:
            game = self.pick_games_list[index][0]
            title = self.pick_games_list[index][0]
            path = self.pick_games_list[index][1]
            AddBox(self.parent, game=game, title=title, path=path)
        else:
            AddBox(self.parent)
        self.on_closing()

class SessionNote(Frame):
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

        Label(win, text="{}, {}".format(self.session.user_app, self.session.started.strftime('%Y-%m-%d %H:%M:%S'))).pack()

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
                text = Text(self, width=60, height=3)
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
        valid = True
        for key in self.new_values:
            if self.settings_template[key].get('validate'):
                try:
                    if self.settings_template[key].get('validate')(self.new_values[key]()) is False:
                        valid = False
                        messagebox.showerror(
                            "Error in {}".format(self.settings_template[key]['name']),
                            "Invalid value for {}".format(self.settings_template[key]['name']))
                except ValueError as e:
                    valid = False
                    messagebox.showerror(
                        "Error in {}".format(self.settings_template[key]['name']),
                        "Error in {}: {}".format(key[0], str(e)))
        return valid

    def save_settings(self):
        if self.validate_settings():
            for key in self.new_values:
                if self.settings_template[key]['type'] == 'list':
                    DBConfig.delete(*key)
                    for v in self.new_values[key]():
                        DBConfig.set(*key, v, append=True)
                else:
                    DBConfig.set(*key, self.new_values[key]())

class SettingsBox(Frame):
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

            self.nb = ttk.Notebook(self.win)

            try:
                tab = SettingsTab(self.win, parent.settings_template)
            except Exception:
                logger.exception("Failed to build Application settings tab.")

            self.nb.add(tab, text='Application')

            for p in filter(lambda p: p.plugin.get_settings_template(), parent.installed_plugins.values()):
                try:
                    tab = SettingsTab(self.win, p.plugin.get_settings_template())
                    self.nb.add(tab, text=p.plugin.SETTINGS_TAB_NAME)
                except Exception:
                    logger.exception("Failed to add tab for plugin %r", p)

            self.nb.grid()
            Button(self.win, text="Save", command=self.save_settings).grid(sticky=E+W)
            Button(self.win, text="Cancel", command=self.on_closing).grid(sticky=E+W)

            self.win.protocol("WM_DELETE_WINDOW", self.on_closing)
        except:
            logger.exception("Failed to build settings box.")
            raise

    def on_closing(self):
        self.config.set('geometry', '+' + self.win.winfo_geometry().split('+', maxsplit=1)[1])
        self.destroy()

    def save_settings(self):
        try:
            valid = True
            for t in self.nb.tabs():
                if not self.nametowidget(t).validate_settings():
                    valid = False
            if valid:
                for t in self.nb.tabs():
                    self.nametowidget(t).save_settings()
                self.parent.event_generate("<<SettingsUpdated>>")
                self.on_closing()
        except Exception as e:
            logger.exception("Failed to save settings.")
            messagebox.showerror(
                "Failed to save settings",
                ("Failed to save settings: {}\n"
                 "\n"
                 "More information may be available in the log.").format(str(e)))
            self.on_closing()

class Application(Frame):
    def __init__(self, master=None, installed_plugins=None):
        Frame.__init__(self, master)
        self.RUNNING = None
        self.play_session = None
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
        for p in persistent_plugins:
            try:
                self.persistent_plugins.append(p(self))
                logger.debug("Plugin activated: %s", p.__name__)
            except Exception:
                logger.exception("Could not initialize plugin %r.", p)

        master.grid_columnconfigure(0, weight=1)

        self.createWidgets()

        def update_log_level(e):
            if self.config.getboolean('debug', fallback=False):
                logging.getLogger().setLevel(logging.DEBUG)
                logger.info("Log level set to DEBUG")
            else:
                logging.getLogger().setLevel(logging.INFO)
                logger.info("Log level set to INFO")

        self.bind("<<SettingsUpdated>>", update_log_level, "+")

    settings_template = OrderedDict()
    settings_template[('Application', 'confirm_exit')] = {
        'name' : 'Confirm exit',
        'type' : 'bool',
        'default' : True,
        'hint' : "If checked, gamest will ask for confirmation before exiting.",
    }
    settings_template[('Application', 'debug')] = {
        'name' : 'Debug',
        'type' : 'bool',
        'default' : False,
        'hint' : "Write additional debug messages to the log file.",
    }

    def do_report(self):
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
        self.note_button = Button(self, text="Edit Note", command=lambda: SessionNote(self, self.play_session), state=DISABLED)
        self.note_button.grid(row=4, column=1)
        Button(self, text="Add Time", command=lambda: AddTimeBox(self)).grid(row=5, column=0)
        self.manual_session_button = Button(self, text="Begin Manual Session", command=lambda: ManualSessionSelector(self), state=NORMAL)
        self.manual_session_button.grid(row=5, column=1)

        self.grid(stick=E+W)

    def run(self):
        try:
            EnumWindows(EnumWindowsProc(foreach_window), 1)
            if self.RUNNING is not None:
                self.manual_session_button.config(state=DISABLED)
                self.rtlabel.config(fg='green')
                self.started = datetime.datetime.now()
                self.RUNNING = (self.RUNNING[0], Session.merge(self.RUNNING[1]))
                self.play_session = PlaySession(user_app=self.RUNNING[1], started=self.started)
                Session.add(self.play_session)
                Session.flush()
                for p in self.session_plugins:
                    try:
                        self.active_plugins.append(p(self))
                        logger.debug("Plugin activated: %s", p.__name__)
                    except plugins.UnsupportedAppError:
                        pass
                    except Exception:
                        logger.exception("Failed to initialize session plugin %r.", p)
                self.event_generate("<<GameStart{}>>".format(self.play_session.id))
                logger.debug("Now running %s", self.RUNNING[1].app.name)
                self.running_text.set("Now running: ")
                self.running_app.set("{} (#{})".format(self.RUNNING[1].app.name, self.RUNNING[1].id))
                self.time_text.set("{}".format(format_time(self.RUNNING[1].app.runtime)))
                self.elapsed_text.set(format_time(0))
                self.sent = False
            if self.RUNNING is None:
                root.after(5000, self.run)
                self.manual_session_button.config(state=NORMAL)
            else:
                root.after(5000, self.wait)
        except:
            logger.exception("Mysterious error")
            root.after(5000, self.run)
        finally:
            root.update()
            Session.commit()

    def wait(self):
        try:
            if self.RUNNING[0].is_running():
                try:
                    elapsed = int((datetime.datetime.now() - self.started).total_seconds())
                    self.play_session.duration = elapsed
                    self.note_button.config(state=NORMAL)
                    self.time_text.set(format_time(self.RUNNING[1].app.runtime))
                    self.elapsed_text.set(format_time(elapsed))
                except:
                    logger.exception("Failure in running branch")
                finally:
                    root.after(5000, self.wait)
            else:
                try:
                    self.rtlabel.config(fg='black')
                    elapsed = int((datetime.datetime.now() - self.started).total_seconds())
                    self.play_session.duration = elapsed
                    self.running_text.set("Last running: ")
                except:
                    logger.exception("Failure in not running branch")
                finally:
                    Session.commit()
                    self.RUNNING = None
                    self.manual_session_button.config(state=NORMAL)
                    self.event_generate("<<GameEnd{}>>".format(self.play_session.id))
                    self.active_plugins = []
                    self.unbind("<<GameStart{}>>".format(self.play_session.id))
                    self.unbind("<<GameEnd{}>>".format(self.play_session.id))
                    root.after(50, self.run)
        except:
            logger.exception("Failure with is_running(), probably")
            self.RUNNING = None
            root.after(50, self.run)
        finally:
            root.update()
            Session.commit()

def main():
    if DBConfig.getboolean('Application', 'debug', fallback=False):
        logging.getLogger().setLevel(logging.DEBUG)
    if not ctypes.windll.shell32.IsUserAnAdmin():
        sys.exit(ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.argv[0], ' '.join(sys.argv[1:]), None, 1))

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
    root.after(1000, appli.run)

    def on_closing():
        if DBConfig.get('Application', 'confirm_exit', type=bool, fallback=True) is False or messagebox.askokcancel("Quit", "Do you want to quit?"):
            if appli.RUNNING is not None:
                logger.debug("appli.RUNNING is not None")
                try:
                    if appli.RUNNING[0].is_running():
                        elapsed = int((datetime.datetime.now() - appli.started).total_seconds())
                        appli.play_session.duration = elapsed
                        Session.commit()
                except:
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
