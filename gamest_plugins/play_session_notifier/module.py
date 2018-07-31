from gamest.plugins import GamestSessionPlugin, NotificationService
from gamest.util import format_time

class PlaySessionNotificationPlugin(GamestSessionPlugin):
    SETTINGS_TAB_NAME = "Play Session Notifier"
    def __init__(self, application):
        super().__init__(application)

        self.running = application.RUNNING
        self.start_job = None

        self.logger.debug(
            "Available notification services: %s",
            list(p.__class__.__name__ for p in filter(
                lambda p: isinstance(p, NotificationService),
                self.application.persistent_plugins)))

        application.bind("<<GameStart{}>>".format(self.play_session.id), self.onGameStart, "+")
        application.bind("<<GameEnd{}>>".format(self.play_session.id), self.onGameEnd, "+")

        self.logger.debug("Plugin initialized.\n\tsend_begin: %r", self.send_begin)

    @property
    def send_begin(self):
        return self.config.getboolean('send_begin', fallback=True)

    @property
    def send_end(self):
        return self.config.getboolean('send_end', fallback=True)

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
        return d

    def onGameStart(self, e):
        self.logger.debug("onGameStart called")
        def _onGameStart():
            self.logger.debug("_onGameStart called")
            self.start_job = None
            if not self.send_begin or not self.running is self.application.RUNNING:
                return
            for s in filter(lambda p: isinstance(p, NotificationService), self.application.persistent_plugins):
                self.logger.debug("About to notify with %s", s.__class__.__name__)
                s.notify('{{user_name}} began playing **{}**.'.format(
                    self.play_session.user_app.app.name))
        self.start_job = self.application.after(30000, _onGameStart)

    def onGameEnd(self, e):
        try:
            self.logger.debug("onGameEnd called")
            if not self.send_end or self.play_session.duration < 30:
                return
            for s in filter(lambda p: isinstance(p, NotificationService), self.application.persistent_plugins):
                s.notify('{{user_name}} played **{}** for {}. Total: {}.'.format(
                    self.play_session.user_app.app.name,
                    format_time(self.play_session.duration),
                    format_time(self.play_session.user_app.app.runtime)))
        except Exception:
            self.logger.exception("Failure in onGameEnd.")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.start_job:
            self.application.after_cancel(self.start_job)
