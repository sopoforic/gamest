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
from tkinter import (Tk, Frame, Toplevel, StringVar, Label, Entry, Button,
    N, S, E, W, DISABLED, NORMAL,
    ttk, messagebox, filedialog)

import psutil

import gamest_plugins
from .db import App, UserApp, PlaySession, Session, set_settings, get_settings, get_settings_list
from .util import format_time
from . import plugins, config, DATA_DIR

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
            start = self.current() + 1 if self.current != -1 else 0
            for index, game in enumerate(self.values[start:]):
                if game.upper().startswith(event.char.upper()):
                    self.current(index+start)
                    return
            else:
                for index, game in enumerate(self.values):
                    if game.upper().startswith(event.char.upper()):
                        self.current(index)
                        return

class AddBox(Frame):
    def __init__(self, parent, game='', path='', title='', seconds='', notes=''):
        Frame.__init__(self, parent)
        self.parent = parent

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
        geometry = get_settings(self.__class__.__name__, 'geometry') or '400x160'
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
        set_settings(self.__class__.__name__, 'geometry', self.win.winfo_geometry())
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

        self.seconds_entry = StringVar()

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = get_settings(self.__class__.__name__, 'geometry') or '400x120'
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
        set_settings(self.__class__.__name__, 'geometry', self.win.winfo_geometry())
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

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = get_settings(self.__class__.__name__, 'geometry') or '400x80'
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
        set_settings(self.__class__.__name__, 'geometry', self.win.winfo_geometry())
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
        self.ua = ua
        self.proc = FakeProcess()
        appli.RUNNING = (self.proc, self.ua)
        self.createWidgets()

        self.win.protocol("WM_DELETE_WINDOW", self.end_session)

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = get_settings(self.__class__.__name__, 'geometry') or '400x80'
        win.geometry(geometry)
        win.title("Manual Session")

        Label(win, text="A session of {} is in progress.".format(self.ua.app)).grid()
        Button(win, text="End Session", command=self.end_session).grid(row=1)

    def end_session(self):
        set_settings(self.__class__.__name__, 'geometry', self.win.winfo_geometry())
        self.proc.running = False
        self.destroy()

class PickGame(Frame):
    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.parent = parent

        self.pick_games_list = []
        EnumWindows(EnumWindowsProc(self.populate_games), 1)

        self.createWidgets()

    def populate_games(self, hwnd, lParam):
        pid = ctypes.c_ulong()
        length = GetWindowTextLength(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        GetWindowThreadProcessId(hwnd, ctypes.pointer(pid))
        if config['options'].getboolean('visible_only') and (not buff.value or buff.value in trash or not ctypes.windll.user32.IsWindowVisible(hwnd)):
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
        geometry = get_settings(self.__class__.__name__, 'geometry') or '400x80'
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

        Button(win, text="Pick Game", command=self.do_pickgame).grid(row=1, columnspan=2)

    def on_closing(self):
        set_settings(self.__class__.__name__, 'geometry', self.win.winfo_geometry())
        self.destroy()

    def do_pickgame(self):
        index = self.pickgamecombo.current()
        game = self.pick_games_list[index][0]
        title = self.pick_games_list[index][0]
        path = self.pick_games_list[index][1]
        AddBox(self.parent, game=game, title=title, path=path)
        self.on_closing()

class SessionNote(Frame):
    def __init__(self, parent, session):
        Frame.__init__(self, parent)
        self.parent = parent
        self.session = session

        self.createWidgets()

    def createWidgets(self):
        win = Toplevel(self)
        self.win = win
        geometry = get_settings(self.__class__.__name__, 'geometry') or '600x400'
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
        set_settings(self.__class__.__name__, 'geometry', self.win.winfo_geometry())
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

class Application(Frame):
    def __init__(self, master=None, persistent_plugins=None, session_plugins=None):
        Frame.__init__(self, master)
        self.RUNNING = None
        self.play_session = None
        self.config = config

        self.active_plugins = []
        self.session_plugins = session_plugins or []
        self.persistent_plugins = []
        if persistent_plugins:
            for p in persistent_plugins:
                try:
                    self.persistent_plugins.append(p(self))
                    logger.debug("Plugin activated: %s", p.__name__)
                except Exception:
                    logger.exception("Could not initialize plugin %r.", p)

        master.grid_columnconfigure(0, weight=1)

        self.createWidgets()

    def do_report(self):
        filename = filedialog.asksaveasfilename(
            initialdir=DATA_DIR,
            initialfile='report.html',
            title="Save report as...",
            filetypes=(("HTML files","*.html"),),)
        if filename:
            html = generate_report()
            with open(filename, 'wb') as outfile:
                outfile.write(html.encode('utf_8'))
            path = 'file://' + os.path.abspath(filename)
            webbrowser.open(path,new=2)

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

        Button(self, text="Pick Game", command=lambda: PickGame(self)).grid(row=3, column=0)
        Button(self, text="Add Game Manually", command=lambda: AddBox(self)).grid(row=3, column=1)
        Button(self, text="Save report", command=self.do_report).grid(row=4, column=0)
        self.note_button =  Button(self, text="Edit Note", command=lambda: SessionNote(self, self.play_session), state=DISABLED)
        self.note_button.grid(row=4, column=1)
        Button(self, text="Add Time", command=lambda: AddTimeBox(self)).grid(row=5, column=0)
        self.manual_session_button =  Button(self, text="Begin Manual Session", command=lambda: ManualSessionSelector(self), state=NORMAL)
        self.manual_session_button.grid(row=5, column=1)

        self.grid(stick=E+W)

    def run(self):
        try:
            EnumWindows(EnumWindowsProc(foreach_window), 1)
            if self.RUNNING is not None:
                self.manual_session_button.config(state=DISABLED)
                self.rtlabel.config(fg='green')
                self.started = datetime.datetime.now()
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
    if not ctypes.windll.shell32.IsUserAnAdmin():
        sys.exit(ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.argv[0], ' '.join(sys.argv[1:]), None, 1))

    from pkg_resources import get_distribution, DistributionNotFound
    try:
        logger.info("Starting gamest %s", pkg_resources.get_distribution('gamest').version)
    except pkg_resources.DistributionNotFound:
        logger.info("Starting gamest (version not available)")

    global root
    global appli
    root = Tk()
    root.wm_title("Gamest")
    geometry = get_settings('Application', 'geometry') or '400x150'
    root.geometry(geometry)

    installed_plugins = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in pkgutil.iter_modules(gamest_plugins.__path__, gamest_plugins.__name__ + ".")
    }

    for p in filter(lambda p: issubclass(p.plugin, plugins.GamestPlugin), installed_plugins.values()):
        p.plugin.copy_sample_config()

    logger.debug("Plugins found: %s", list(installed_plugins.keys()))

    persistent_plugins = [
        p.plugin
        for p in installed_plugins.values()
        if hasattr(p, 'plugin') and issubclass(p.plugin, plugins.GamestPersistentPlugin)
    ]

    logger.debug("Persistent plugins to activate: %s", ', '.join(p.__name__ for p in persistent_plugins))

    session_plugins = [
        p.plugin
        for p in installed_plugins.values()
        if hasattr(p, 'plugin') and issubclass(p.plugin, plugins.GamestSessionPlugin)
    ]

    logger.debug("Session plugins to activate: %s", ', '.join(p.__name__ for p in session_plugins))

    appli = Application(master=root, persistent_plugins=persistent_plugins, session_plugins=session_plugins)
    root.after(1000, appli.run)

    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            if appli.RUNNING is not None:
                logger.debug("appli.RUNNING is not None")
                try:
                    if appli.RUNNING[0].is_running():
                        elapsed = int((datetime.datetime.now() - appli.started).total_seconds())
                        appli.play_session.duration = elapsed
                        Session.commit()
                except:
                    logger.exception("Failed is_running check on shutdown")
            set_settings('Application', 'geometry', root.winfo_geometry())
            logger.debug("Committing and quitting.")
            Session.commit()
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    appli.mainloop()

if __name__ == '__main__':
    main()
