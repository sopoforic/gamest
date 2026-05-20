import os
os.environ['GAMEST_DB_PATH'] = ':memory:'

from unittest.mock import MagicMock
import pytest
from gamest.db import Session, Base, engine
from gamest.plugins import NotificationService


class FakeNotificationService(NotificationService):
    def __init__(self):
        self.received = []

    def notify(self, msg):
        self.received.append(msg)

    def cleanup(self):
        pass


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Session.remove()


@pytest.fixture
def mock_application():
    app = MagicMock()
    app.RUNNING = object()
    app.persistent_plugins = []
    app.play_session = MagicMock()
    app.play_session.id = 1
    return app
