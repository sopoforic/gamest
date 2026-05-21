import json
import re
from collections import defaultdict

import getpass
import psutil

from gamest import db
from gamest.plugins import IdentifierPlugin

trash_names = {
    'bash',
    'cat',
    'dbus-daemon',
    'Discord',
    'dropbox',
    'emacs',
    'gamest',
    'gpg-agent',
    'gvfsd',
    'nautilus',
    'node',
    'pyls',
    'pulseaudio',
    'python3',
    'sh',
    'ssh-agent',
    'snap-store',
    'spotify',
    'steam',
    'steamwebhelper',
    'steamwebhelper.',
    'sqlite3',
    'systemd',
    'Xorg',
    # Windows
    'chrome.exe',
    'cmd.exe',
    'conhost.exe',
    'Discord.exe',
    'dllhost.exe',
    'Dropbox.exe',
    'explorer.exe',
    'py.exe',
    'python.exe',
    'pythonw.exe',
    'Registry',
    'rundll32.exe',
    'SearchIndexer.exe',
    'smartscreen.exe',
    'smss.exe',
    'steam.exe',
    'steamwebhelper.exe',
    'svchost.exe',
    'System',
    'SystemSettings.exe',
    'System Idle Process',
    'taskhostw.exe',
    'unsecapp.exe',
    'WmiPrvSE.exe',
}
trash_regex = [
    r'evolution-.+',
    r'gnome-.+',
    r'gsd-.+',
    r'gvfs-.+',
    r'gvfsd-.+',
    r'ibus-.+',
    r'xdg-.+',
]


class ProcessIdentifierPlugin(IdentifierPlugin):
    SETTINGS_TAB_NAME = "Process Identifier"
    def __init__(self, application):
        super().__init__(application)

        self.username = getpass.getuser()
        self._uas = defaultdict(list)
        self._checked_procs = set()
        trash_regex.extend(r for r in self.config.getlist('trash_names') if r)

        def update_trash_names(event):
            del event
            trash_regex.extend(self.config.getlist('trash_names'))
        application.bind("<<SettingsUpdated>>", update_trash_names, "+")

        self.logger.debug("ProcessIdentifierPlugin initialized.")

    @property
    def uas(self):
        if not self._uas:
            q = db.Session.query(db.UserApp).filter(
                db.UserApp.identifier_plugin == self.__class__.__name__)
            self._uas = defaultdict(list)
            for ua in q:
                data = json.loads(ua.identifier_data)
                if exe := data.get('exe'):
                    self._uas[exe].append((ua.id, data.get('cmdline')))

        return self._uas

    @classmethod
    def get_settings_template(cls):
        d = super().get_settings_template()

        d[(cls.__name__, 'trash_names')] = {
            'name' : 'Ignore',
            'type' : 'list',
            'lines': 8,
            'hint' : ("Process names to ignore. May be regular expressions. Put "
                      "one name per line."),
        }

        return d

    def _iter_survivors(self):
        return (p for p in psutil.process_iter(['name', 'create_time'])
                if p.info.get('name')
                and p.info['name'] not in trash_names
                and not any(re.match(t, p.info['name']) for t in trash_regex))

    def candidates(self):
        procs = []
        for p in self._iter_survivors():
            try:
                with p.oneshot():
                    username = p.username()
                    exe = p.exe()
                    cmdline = p.cmdline()
                    create_time = p.create_time()
                if username.endswith(self.username):
                    procs.append((p, exe, cmdline, create_time))
            except Exception:
                pass

        procs.sort(key=lambda x: x[3], reverse=True)

        candidates = []
        for p, exe, cmdline, _ in procs:
            try:
                candidates.append(db.UserApp(
                    note=p.info['name'],
                    identifier_plugin=self.__class__.__name__,
                    identifier_data=json.dumps(
                        {
                            'exe': exe,
                            'cmdline': ' '.join(cmdline).rstrip() if cmdline else '',
                        }
                    )
                ))
            except Exception:
                self.logger.exception("Couldn't add candidate: %r", p)

        return candidates

    def identify_game(self):
        survivors = {(p.pid, p.info['create_time']): p for p in self._iter_survivors()}

        self._checked_procs &= survivors.keys()

        candidates = []
        for key, p in survivors.items():
            if key in self._checked_procs:
                continue
            try:
                with p.oneshot():
                    if not p.username().endswith(self.username):
                        continue
                    candidates.append((p, p.exe(), p.cmdline()))
            except psutil.NoSuchProcess:
                continue
            except Exception:
                self._checked_procs.add(key)
                continue

        # Oldest process first.
        candidates.sort(key=lambda x: x[0].info['create_time'] or 0)

        for p, exe, cmdline in candidates:
            if uas := self.uas.get(exe):
                for ua_id, match_cmdline in uas:
                    if not match_cmdline or ' '.join(cmdline).startswith(match_cmdline):
                        return (p, db.Session.query(db.UserApp).get(ua_id))
            self._checked_procs.add((p.pid, p.info['create_time']))

        return None

    def clear_cache(self):
        self._uas = {}
        self._checked_procs = set()
