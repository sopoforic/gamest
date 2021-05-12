import json
import re

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
        self._uas = {}
        trash_regex.extend(r for r in self.config.getlist('trash_names') if r)

        def update_trash_names(event):
            del event
            trash_regex.extend(self.config.getlist('trash_names'))
        application.bind("<<SettingsUpdated>>", update_trash_names, "+")

        self.logger.debug("ProcessIdentifierPlugin initialized.")

    @property
    def uas(self):
        if not self._uas:
            self._uas = {ua.id: json.loads(ua.identifier_data)
                         for ua in db.Session.query(db.UserApp).filter(
                                 db.UserApp.identifier_plugin == self.__class__.__name__)}

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

    def candidates(self):
        procs = [p
                 for p in psutil.process_iter(['name', 'username', 'exe', 'cmdline', 'create_time'])
                 if p.info['username'].endswith(self.username)
                 and p.info['name'] not in trash_names
                 and not any(re.match(t, p.info['name']) for t in trash_regex)]

        procs.sort(key=lambda p: p.info['create_time'], reverse=True)

        candidates = []
        for p in procs:
            try:
                candidates.append(db.UserApp(
                    note=p.info['name'],
                    identifier_plugin=self.__class__.__name__,
                    identifier_data=json.dumps(
                        {
                            'exe': p.info['exe'],
                            'cmdline': ' '.join(p.info['cmdline']).rstrip() if p.info['cmdline'] else '',
                        }
                    )
                ))
            except Exception:
                self.logger.exception("Couldn't add candidate: %r", p)

        return candidates

    def identify_game(self):
        candidates = [p
                      for p in psutil.process_iter(['name', 'username', 'exe', 'cmdline', 'create_time'])
                      if p.info['username'].endswith(self.username)
                      and p.info['name'] not in trash_names
                      and not any(re.match(t, p.info['name']) for t in trash_regex)]

        # This way we will catch the oldest process first.
        candidates.sort(key=lambda c: c.info['create_time'])

        for c in candidates:
            for ua_id, data in self.uas.items():
                if c.info['exe'] == data.get('exe'):
                    if (not data.get('cmdline') or
                            ' '.join(c.info['cmdline']).startswith(data.get('cmdline'))):
                        return (c, db.Session.query(db.UserApp).get(ua_id))

        return None

    def clear_cache(self):
        self._uas = {}
