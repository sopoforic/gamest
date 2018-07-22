import configparser
import logging
import os
import pkg_resources
import weakref
from shutil import copyfile

from . import DATA_DIR
from .errors import UnsupportedAppError

class GamestPlugin:
    def __init__(self, application):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        self.application = application

        self.config = configparser.ConfigParser(delimiters=('=',))

        CONFIG_PATH = os.path.join(DATA_DIR, '{}.conf'.format(self.__class__.__name__))
        self.config.read([CONFIG_PATH])
        if not os.path.exists(CONFIG_PATH):
            PKG = self.__module__.rsplit('.', 1)[0]
            if pkg_resources.resource_exists(PKG, '{}.conf.default'.format(self.__class__.__name__)):
                copyfile(pkg_resources.resource_filename(PKG, '{}.conf.default'.format(self.__class__.__name__)), CONFIG_PATH)

class GamestPersistentPlugin(GamestPlugin):
    pass

class GamestSessionPlugin(GamestPlugin):
    start_bind = None
    end_bind = None

    def __init__(self, application):
        super().__init__(application)
        self.play_session = application.play_session

        weakstart = weakref.WeakMethod(self.onGameStart)
        weakend = weakref.WeakMethod(self.onGameEnd)

        self.start_bind = application.bind("<<GameStart>>", lambda e: weakstart()(e), "+")
        self.end_bind = application.bind("<<GameEnd>>", lambda e: weakend()(e), "+")

    def onGameStart(self, e):
        raise NotImplementedError

    def onGameEnd(self, e):
        raise NotImplementedError

    def __del__(self):
        self.logger.debug("__del__ called on %r", self)
        self.cleanup()
    
    def cleanup(self):
        if self.start_bind:
            self.application.unbind("<<GameStart>>", self.start_bind)
            self.start_bind = None
        if self.end_bind:
            self.application.unbind("<<GameEnd>>", self.end_bind)
            self.end_bind = None
        self.logger.debug("Removed bindings.")

class NotificationService(GamestPersistentPlugin):
    user_name = None

    def notify(self, msg):
        raise NotImplementedError

class GameReporterPlugin(GamestSessionPlugin):
    PATH_ENDSWITH = []

    def __init__(self, application):
        super().__init__(application)

        self.user_app_id = self.config.getint(self.__class__.__name__, 'user_app_id', fallback=None)

        if self.user_app_id and (self.user_app_id != self.play_session.user_app_id):
            self.logger.debug("User app ID did not match: {} !+ {} (configured)".format(self.play_session.user_app_id, self.user_app_id))
            raise UnsupportedAppError("Current user_app_id is %s, configured user_app_id is %s.", self.play_session.user_app_id, self.user_app_id)
        elif not self.user_app_id and not (self.play_session.user_app.path and any(self.play_session.user_app.path.endswith(p) for p in self.PATH_ENDSWITH)):
            self.logger.debug("Path did not match: {}.".format(self.play_session.user_app.path))
            raise UnsupportedAppError("Current app path does not match a supported path.")

        self.interval = self.config.getint(self.__class__.__name__, 'interval', fallback=30*60*1000)
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
                report_text = report_text + report_details
                for s in filter(lambda p: isinstance(p, NotificationService), self.application.persistent_plugins):
                    s.notify(report_text)
            else:
                self.logger.debug("No difference since report.")
        except:
            self.logger.exception("Failed to build update.")
        finally:
            if self.application.RUNNING and self.play_session is self.application.play_session:
                self.job = self.application.after(self.interval, self.report_update)

    def onGameStart(self, e):
        self.job = self.application.after(35000, self.report_update)

    def onGameEnd(self, e):
        self.logger.debug("onGameEnd called")
        if self.job:
            self.application.after_cancel(self.job)
        self.report_update(game_end=True)
        self.cleanup()
