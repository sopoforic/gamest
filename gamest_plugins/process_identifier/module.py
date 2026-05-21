import json
import re
from collections import defaultdict

import getpass
import psutil

from sqlalchemy import select

from gamest import db
from gamest.plugins import IdentifierPlugin

trash_names = {
    'Discord',
    'Xorg',
    'bash',
    'cat',
    'dbus-daemon',
    'dropbox',
    'emacs',
    'gamest',
    'gpg-agent',
    'gvfsd',
    'nautilus',
    'node',
    'pulseaudio',
    'pyls',
    'python3',
    'sh',
    'snap-store',
    'spotify',
    'sqlite3',
    'ssh-agent',
    'steam',
    'steamwebhelper',
    'steamwebhelper.',
    'systemd',
    # Windows
    'AppleMobileDeviceProcess.exe',
    'ApplicationFrameHost.exe',
    'CefSharp.BrowserSubprocess.exe',
    'CrossDeviceResume.exe',
    'CrossDeviceService.exe',
    'DAX3API.exe',
    'Discord.exe',
    'Docker Desktop.exe',
    'Dropbox.exe',
    'EPDCtrl.exe',
    'EPDService.exe',
    'EdgeGameAssist.exe',
    'GOG Galaxy Notifications Renderer.exe',
    'GalaxyClient Helper.exe',
    'GalaxyClient.exe',
    'GalaxyCommunication.exe',
    'GameInputRedistService.exe',
    'GameInputSvc.exe',
    'ITSPowerMode.exe',
    'LockApp.exe',
    'LsaIso.exe',
    'MemCompression',
    'Microsoft.CmdPal.UI.exe',
    'OpenConsole.exe',
    'PhoneExperienceHost.exe',
    'PowerMgr.exe',
    'PowerToys.Peek.UI.exe',
    'PowerToys.exe',
    'Registry',
    'RuntimeBroker.exe',
    'SearchHost.exe',
    'SearchIndexer.exe',
    'SecurityHealthSystray.exe',
    'ShellExperienceHost.exe',
    'ShellHost.exe',
    'Slack.exe',
    'Spotify.exe',
    'SpotifyLauncher.exe',
    'StartMenuExperienceHost.exe',
    'StoreDesktopExtension.exe',
    'System Idle Process',
    'System',
    'SystemSettings.exe',
    'TabTip.exe',
    'TextInputHost.exe',
    'UserOOBEBroker.exe',
    'WUDFCompanionHost.exe',
    'WUDFHost.exe',
    'WidgetService.exe',
    'Widgets.exe',
    'WindowsPackageManagerServer.exe',
    'WindowsTerminal.exe',
    'WmiPrvSE.exe',
    'XboxGameBarSpotify.exe',
    'XboxPcAppFT.exe',
    'backgroundTaskHost.exe',
    'chrome.exe',
    'cmd.exe',
    'com.docker.backend.exe',
    'com.docker.build.exe',
    'conhost.exe',
    'crashhelper.exe',
    'crashpad_handler.exe',
    'csrss.exe',
    'ctfmon.exe',
    'dasHost.exe',
    'dllhost.exe',
    'dwm.exe',
    'explorer.exe',
    'firefox.exe',
    'fontdrvhost.exe',
    'gamest.exe',
    'ipf_helper.exe',
    'ipfsvc.exe',
    'itch.exe',
    'lsass.exe',
    'msedge.exe',
    'msedgewebview2.exe',
    'msrdc.exe',
    'nfsclnt.exe',
    'powershell.exe',
    'py.exe',
    'python.exe',
    'pythonw.exe',
    'rundll32.exe',
    'services.exe',
    'sihost.exe',
    'smartscreen.exe',
    'smss.exe',
    'spoolsv.exe',
    'steam.exe',
    'steamservice.exe',
    'steamwebhelper.exe',
    'svchost.exe',
    'taskhostw.exe',
    'tposd.exe',
    'unsecapp.exe',
    'vmcompute.exe',
    'vmmemWSL',
    'vmms.exe',
    'vmwp.exe',
    'wininit.exe',
    'winlogon.exe',
    'wsl.exe',
    'wslg.exe',
    'wslhost.exe',
    'wslrelay.exe',
    'wslservice.exe',
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

        self.username = getpass.getuser().split('\\')[-1]
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
            q = select(db.UserApp).\
                where(db.UserApp.identifier_plugin == self.__class__.__name__)
            uas = db.Session.scalars(q)
            self._uas = defaultdict(list)
            for ua in uas:
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
                if username.split('\\')[-1] == self.username:
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
                    if p.username().split('\\')[-1] != self.username:
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
                        return (p, db.Session.get(db.UserApp, ua_id))
            self._checked_procs.add((p.pid, p.info['create_time']))

        return None

    def clear_cache(self):
        self._uas = {}
        self._checked_procs = set()
