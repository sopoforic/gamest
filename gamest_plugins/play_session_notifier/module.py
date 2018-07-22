from gamest.plugins import GamestSessionPlugin, NotificationService
from gamest.util import format_time

class PlaySessionNotificationPlugin(GamestSessionPlugin):
    def __init__(self, application):
        super().__init__(application)

        self.running = application.RUNNING
        self.send_begin = application.config.getboolean('PlaySessionNotificationPlugin', 'send_begin', fallback=False)
        self.start_job = None

        self.logger.debug("Plugin initialized.\n\tsend_begin: %r", self.send_begin)

    def onGameStart(self, e):
        self.logger.debug("onGameStart called")
        def _onGameStart():
            self.logger.debug("_onGameStart called")
            self.start_job = None
            if not self.send_begin or not self.running is self.application.RUNNING:
                return
            for s in filter(lambda p: isinstance(p, NotificationService), self.application.persistent_plugins):
                s.notify('{{user_name}} began playing **{}**.'.format(
                    self.play_session.user_app.app.name))
        self.start_job = self.application.after(30000, _onGameStart)

    def onGameEnd(self, e):
        try:
            self.logger.debug("onGameEnd called")
            if self.start_job:
                self.application.after_cancel(self.start_job)
            if (self.play_session.duration < 30):
                return
            for s in filter(lambda p: isinstance(p, NotificationService), self.application.persistent_plugins):
                s.notify('{{user_name}} played **{}** for {}. Total: {}.'.format(
                    self.play_session.user_app.app.name,
                    format_time(self.play_session.duration),
                    format_time(self.play_session.user_app.app.runtime)))
        except:
            self.logger.exception("Failure in onGameEnd.")
        finally:
            self.cleanup()