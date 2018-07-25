import configparser
import logging
import os
import pkg_resources
from shutil import copyfile

from . import DATA_DIR
from .errors import UnsupportedAppError, InvalidConfigurationError

class GamestPlugin:
    def __init__(self, application):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        self.application = application

        self.config = configparser.ConfigParser(delimiters=('=',))

        CONFIG_PATH = os.path.join(DATA_DIR, '{}.conf'.format(self.__class__.__name__))
        self.config.read([CONFIG_PATH])

    @classmethod
    def copy_sample_config(cls):
        CONFIG_PATH = os.path.join(DATA_DIR, '{}.conf'.format(cls.__name__))
        if not os.path.exists(CONFIG_PATH):
            PKG = cls.__module__.rsplit('.', 1)[0]
            if pkg_resources.resource_exists(PKG, '{}.conf.default'.format(cls.__name__)):
                copyfile(pkg_resources.resource_filename(PKG, '{}.conf.default'.format(cls.__name__)), CONFIG_PATH)

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
    PATH_ENDSWITH = []

    def __init__(self, application):
        super().__init__(application)

        self.user_app_id = self.config.get(self.__class__.__name__, 'user_app_id', fallback='')
        try:
            self.user_app_ids = [int(i) for i in self.user_app_id.splitlines()]
        except ValueError:
            self.logger.warning("Invalid UserApp ID in %s.conf: %r",
                self.__class__.__name__,
                self.user_app_id)
            raise InvalidConfigurationError("Invalid UserApp ID in {}.conf: {!r}".format(
                self.__class__.__name__,
                self.user_app_id))

        if self.user_app_ids and (self.play_session.user_app_id not in self.user_app_ids):
            self.logger.debug("User app ID did not match: %s not in %s (configured)",
                self.play_session.user_app_id,
                ', '.join(str(i) for i in self.user_app_ids))
            raise UnsupportedAppError("Current user_app_id: {}. Configured: {}.".format(
                self.play_session.user_app_id,
                ', '.join(str(i) for i in self.user_app_ids)))
        elif not self.user_app_ids and not (self.play_session.user_app.path and any(self.play_session.user_app.path.endswith(p) for p in self.PATH_ENDSWITH)):
            self.logger.debug("Path did not match: %s.", self.play_session.user_app.path)
            raise UnsupportedAppError("Current app path does not match a supported path.")

        self.send_begin = self.config.getboolean(self.__class__.__name__, 'send_begin', fallback=True)
        self.send_end = self.config.getboolean(self.__class__.__name__, 'send_end', fallback=True)

        self.add_status_updates = self.config.getboolean(self.__class__.__name__, 'add_status_updates', fallback=True)
        self.interval = self.config.getint(self.__class__.__name__, 'interval', fallback=60*60*1000)
        self.job = None

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
                self.job = self.application.after(self.interval, self.report_update)

    def onGameStart(self, e):
        self.logger.debug("onGameStart called")
        if self.send_begin:
            self.job = self.application.after(35000, self.report_update)

    def onGameEnd(self, e):
        self.logger.debug("onGameEnd called")
        if self.send_end:
            self.report_update(game_end=True)
        self.cleanup()

    def cleanup(self):
        if self.job:
            self.application.after_cancel(self.job)
