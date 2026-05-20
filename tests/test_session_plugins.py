import pytest
from unittest.mock import MagicMock, patch

from gamest.errors import UnsupportedAppError
from gamest.plugins import GameReporterPlugin
from gamest_plugins.play_session_notifier.module import PlaySessionNotificationPlugin
from tests.conftest import FakeNotificationService


class ConcreteReporter(GameReporterPlugin):
    PATH_ENDSWITH = ['.exe']

    def get_report(self):
        return 'report text'


@pytest.fixture
def notifier(mock_application):
    return PlaySessionNotificationPlugin(mock_application)


@pytest.fixture
def notifier_with_service(mock_application):
    svc = FakeNotificationService()
    mock_application.persistent_plugins = [svc]
    mock_application.play_session.user_app.app.name = 'Test Game'
    mock_application.play_session.user_app.app.runtime = 3600
    mock_application.play_session.duration = 60
    plugin = PlaySessionNotificationPlugin(mock_application)
    return plugin, svc, mock_application


def test_game_end_send_end_false_no_notify(notifier_with_service):
    plugin, svc, app = notifier_with_service
    app.play_session.duration = 60
    with patch.object(type(plugin), 'send_end', new_callable=lambda: property(lambda self: False)):
        plugin.onGameEnd(None)
    assert svc.received == []

def test_game_end_short_duration_no_notify(notifier_with_service):
    plugin, svc, app = notifier_with_service
    app.play_session.duration = 29
    plugin.onGameEnd(None)
    assert svc.received == []

def test_game_end_no_services_no_error(notifier):
    notifier.application.play_session.duration = 60
    notifier.onGameEnd(None)

def test_game_end_notifies_with_correct_text(notifier_with_service):
    plugin, svc, app = notifier_with_service
    plugin.onGameEnd(None)
    assert len(svc.received) == 1
    msg = svc.received[0]
    assert 'Test Game' in msg
    assert '1 minute' in msg
    assert '1 hour' in msg

def test_game_end_exception_in_notify_still_cleans_up(notifier_with_service):
    plugin, svc, app = notifier_with_service
    svc.notify = MagicMock(side_effect=RuntimeError("boom"))
    plugin.onGameEnd(None)
    app.after_cancel.assert_not_called()

def test_cleanup_cancels_start_job(notifier):
    job = object()
    notifier.start_job = job
    notifier.cleanup()
    notifier.application.after_cancel.assert_called_once_with(job)

def test_cleanup_noop_when_no_job(notifier):
    notifier.start_job = None
    notifier.cleanup()
    notifier.application.after_cancel.assert_not_called()


def _extract_scheduled_callback(app):
    _, callback = app.after.call_args[0]
    return callback


def test_game_start_schedules_callback(notifier):
    notifier.onGameStart(None)
    notifier.application.after.assert_called_once()
    delay, _ = notifier.application.after.call_args[0]
    assert delay == 30000

def test_game_start_callback_send_begin_false(notifier_with_service):
    plugin, svc, app = notifier_with_service
    with patch.object(type(plugin), 'send_begin', new_callable=lambda: property(lambda self: False)):
        plugin.onGameStart(None)
        callback = _extract_scheduled_callback(app)
        callback()
    assert svc.received == []

def test_game_start_callback_running_mismatch(notifier_with_service):
    plugin, svc, app = notifier_with_service
    plugin.onGameStart(None)
    callback = _extract_scheduled_callback(app)
    app.RUNNING = object()
    callback()
    assert svc.received == []

def test_game_start_callback_notifies(notifier_with_service):
    plugin, svc, app = notifier_with_service
    plugin.onGameStart(None)
    callback = _extract_scheduled_callback(app)
    callback()
    assert len(svc.received) == 1
    assert 'Test Game' in svc.received[0]


def test_reporter_user_app_id_not_in_configured_raises(mock_application):
    from gamest.db import Session, Settings
    mock_application.play_session.user_app_id = 5
    mock_application.play_session.user_app.path = '/games/mygame.exe'
    Session.add(Settings(owner='ConcreteReporter', key='user_app_ids', value='99'))
    Session.commit()
    with pytest.raises(UnsupportedAppError):
        ConcreteReporter(mock_application)

def test_reporter_user_app_id_in_configured_succeeds(mock_application):
    from gamest.db import Session, Settings
    mock_application.play_session.user_app_id = 5
    mock_application.play_session.user_app.path = '/games/mygame.exe'
    Session.add(Settings(owner='ConcreteReporter', key='user_app_ids', value='5'))
    Session.commit()
    ConcreteReporter(mock_application).cleanup()

def test_reporter_no_ids_path_matches_succeeds(mock_application):
    mock_application.play_session.user_app_id = 5
    mock_application.play_session.user_app.path = '/games/mygame.exe'
    ConcreteReporter(mock_application).cleanup()

def test_reporter_no_ids_path_no_match_raises(mock_application):
    mock_application.play_session.user_app_id = 1
    mock_application.play_session.user_app.path = '/games/mygame'
    with pytest.raises(UnsupportedAppError):
        ConcreteReporter(mock_application)

def test_reporter_no_ids_path_none_raises(mock_application):
    mock_application.play_session.user_app_id = 1
    mock_application.play_session.user_app.path = None
    with pytest.raises(UnsupportedAppError):
        ConcreteReporter(mock_application)


@pytest.fixture
def reporter(mock_application):
    mock_application.play_session.user_app_id = 5
    mock_application.play_session.user_app.path = '/games/mygame.exe'
    mock_application.persistent_plugins = [FakeNotificationService()]
    mock_application.RUNNING = True
    plugin = ConcreteReporter(mock_application)
    plugin.application = mock_application
    plugin.play_session = mock_application.play_session
    plugin.play_session.user_app.app.name = 'My Game'
    return plugin


def test_report_update_in_progress_text(reporter):
    reporter.report_update(game_end=False)
    svc = reporter.application.persistent_plugins[0]
    assert any('is playing' in m for m in svc.received)

def test_report_update_game_end_text(reporter):
    reporter.report_update(game_end=True)
    svc = reporter.application.persistent_plugins[0]
    assert any('played' in m for m in svc.received)
