import logging
from collections import OrderedDict
from typing import List

from .db import DBConfig
from .errors import UnsupportedAppError

class GamestPlugin:
    SETTINGS_TAB_NAME = "Plugin"
    def __init__(self, application):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        self.application = application

        self.config = DBConfig(owner=self.__class__.__name__)

    def cleanup(self):
        raise NotImplementedError

    @classmethod
    def get_settings_template(cls):
        return OrderedDict()

class GamestPersistentPlugin(GamestPlugin):
    pass

class GamestSessionPlugin(GamestPlugin):
    start_bind = None
    end_bind = None

    def __init__(self, application):
        super().__init__(application)
        self.play_session = application.play_session

class NotificationService(GamestPersistentPlugin):
    user_name = None

    def notify(self, msg):
        raise NotImplementedError

class GameReporterPlugin(GamestSessionPlugin):
    PATH_ENDSWITH : List[str] = []

    def __init__(self, application):
        super().__init__(application)

        if self.user_app_ids and (self.play_session.user_app_id not in self.user_app_ids):
            self.logger.debug(
                "User app ID did not match: %s not in %s (configured)",
                self.play_session.user_app_id,
                ', '.join(str(i) for i in self.user_app_ids))
            raise UnsupportedAppError(
                "Current user_app_id: {}. Configured: {}.".format(
                    self.play_session.user_app_id,
                    ', '.join(str(i) for i in self.user_app_ids)))
        elif not self.user_app_ids and not (self.play_session.user_app.path and any(self.play_session.user_app.path.endswith(p) for p in self.PATH_ENDSWITH)):
            self.logger.debug("Path did not match: %s.", self.play_session.user_app.path)
            raise UnsupportedAppError("Current app path does not match a supported path.")

        self.job = None

    @property
    def user_app_ids(self):
        return self.config.getlist('user_app_ids', type=int)

    @property
    def send_begin(self):
        return self.config.getboolean('send_begin', fallback=True)

    @property
    def send_end(self):
        return self.config.getboolean('send_end', fallback=True)

    @property
    def add_status_updates(self):
        return self.config.getboolean('add_status_updates', fallback=True)

    @property
    def interval(self):
        return self.config.get('interval', type=int, fallback=60)

    @classmethod
    def get_settings_template(cls):
        d = super().get_settings_template()
        d[(cls.__name__, 'send_begin')] = {
            'name' : 'Notify on game begin',
            'type' : 'bool',
            'default' : True,
            'hint' : "If checked, send a notification when a game session begins.",
        }
        d[(cls.__name__, 'send_end')] = {
            'name' : 'Notify on game end',
            'type' : 'bool',
            'default' : True,
            'hint' : "If checked, send a notification when a game session ends.",
        }
        d[(cls.__name__, 'add_status_updates')] = {
            'name' : 'Save updates in DB',
            'type' : 'bool',
            'default' : True,
            'hint' : "If checked, status updates from this plugin will be saved to the database.",
        }
        d[(cls.__name__, 'interval')] = {
            'name' : 'Update interval (minutes)',
            'type' : 'text',
            'validate' : int,
            'default' : '60',
            'hint' : "How often to send updates, in minutes.",
        }
        d[(cls.__name__, 'user_app_ids')] = {
            'name' : 'UserApp IDs',
            'type' : 'list',
            'hint' : ("By default, this plugin determines which game is running based on the "
                      "executable path. This can fail if your executable has an unexpected "
                      "filename or if another game has the same filename. In that case, set the "
                      "UserApp ID to the number displayed when gamest is detecting the game, and "
                      "this plugin will activate only for that app.\n"
                      "\n"
                      "To specify multiple app IDs (e.g. for different game versions), put one ID "
                      "per line.")
        }
        return d

    def get_report(self):
        raise NotImplementedError

    def report_update(self, game_end=False):
        self.logger.debug("report_update called")
        if game_end:
            report_text = "{{user_name}} played **{}**:\n\n".format(self.play_session.user_app.app)
        else:
            report_text = "{{user_name}} is playing **{}**:\n\n".format(self.play_session.user_app.app)
        try:
            report_details = self.get_report()
            if report_details:
                if self.add_status_updates:
                    self.play_session.add_status_update(report_details)
                report_text = report_text + report_details
                for s in filter(lambda p: isinstance(p, NotificationService), self.application.persistent_plugins):
                    s.notify(report_text)
            else:
                self.logger.debug("No difference since report.")
        except Exception:
            self.logger.exception("Failed to build update.")
        finally:
            if self.application.RUNNING and self.play_session is self.application.play_session:
                self.job = self.application.after(self.interval*60*1000, self.report_update)

    def onGameStart(self, e):
        self.logger.debug("onGameStart called")
        if self.send_begin:
            self.job = self.application.after(35000, self.report_update)
        else:
            self.job = self.application.after(self.interval*60*1000, self.report_update)

    def onGameEnd(self, e):
        self.logger.debug("onGameEnd called")
        if self.send_end:
            self.report_update(game_end=True)
        self.cleanup()

    def cleanup(self):
        if self.job:
            self.application.after_cancel(self.job)

class IdentifierPlugin(GamestPersistentPlugin):
    def candidates(self):
        return []

    def identify_game(self):
        return None

    def clear_cache(self):
        pass
