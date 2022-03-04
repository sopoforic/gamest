import logging
import os

import sqlalchemy.ext.declarative
from sqlalchemy import Column, Index, ForeignKey, Integer, Text, Boolean, DateTime
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref, object_session
from sqlalchemy import create_engine
from sqlalchemy.sql import func

from . import DATA_DIR

logger = logging.getLogger(__name__)

Base = declarative_base() # type: sqlalchemy.ext.declarative.api.Base

DBPATH = os.path.join(DATA_DIR, 'gamest.db')

engine = create_engine(r'sqlite:///{}'.format(DBPATH))
Session = scoped_session(sessionmaker(bind=engine))

class App(Base):
    __tablename__ = 'app'
    id = Column(Integer, primary_key=True)

    name = Column(Text, nullable=False)
    disambiguation = Column(Text)

    def __repr__(self):
        return "App(id={}, name={}, disambiguation={})".format(
            self.id, self.name, self.disambiguation)

    def __str__(self):
        return self.name

    @property
    def runtime(self):
        return sum(u.runtime for u in self.user_apps)

class UserApp(Base):
    __tablename__ = 'user_app'
    __table_args__ = (
        Index('user_app_identifier_plugin_data_idx', 'identifier_plugin', 'identifier_data'),
    )
    id = Column(Integer, primary_key=True)

    app_id = Column(Integer, ForeignKey('app.id'), nullable=False, index=True)
    app = relationship('App', backref='user_apps')

    note = Column(Text)
    path = Column(Text, index=True)

    identifier_plugin = Column(Text)
    identifier_data = Column(Text)

    initial_runtime = Column(Integer, nullable=False, default=0)
    window_text = Column(Text, index=True)

    @property
    def runtime(self):
        added = Session.query(func.sum(PlaySession.duration)).filter(
            PlaySession.user_app == self).scalar()
        if not added:
            added = 0
        return self.initial_runtime + added

    def __repr__(self):
        return "UserApp(id={}, app_id={}, path={}, window_text={}, initial_runtime={})".format(
            self.id, self.app_id, self.path, self.window_text, self.initial_runtime)

    def __str__(self):
        return self.app.name

class PlaySession(Base):
    __tablename__ = 'play_session'
    id = Column(Integer, primary_key=True)

    user_app_id = Column(Integer, ForeignKey('user_app.id'), nullable=False, index=True)
    user_app = relationship(
        'UserApp',
        backref=backref('play_sessions', order_by='PlaySession.started.asc()'))

    started = Column(DateTime, nullable=False, default=func.now(), index=True)
    duration = Column(Integer, nullable=False, default=0)
    note = Column(Text)

    def __repr__(self):
        return "PlaySession(id={}, user_app_id={}, started={}, duration={})".format(
            self.id, self.user_app_id, self.started, self.duration)

    @property
    def app(self):
        return self.user_app.app

    def add_status_update(self, note):
        object_session(self).add(StatusUpdate(play_session=self, note=note))

class StatusUpdate(Base):
    __tablename__ = 'status_update'
    id = Column(Integer, primary_key=True)

    play_session_id = Column(Integer, ForeignKey('play_session.id'), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    note = Column(Text)

    play_session = relationship(
        'PlaySession',
        backref=backref('status_updates', order_by='StatusUpdate.timestamp.asc()'))

    def __repr__(self):
        return "StatusUpdate(id={}, play_session_id={}, timestamp={!r})".format(
            self.id, self.play_session_id, self.timestamp)

    def __str__(self):
        return self.note

class Settings(Base):
    __tablename__ = 'settings'
    __table_args__ = (
        Index('settings_owner_key_idx', 'owner', 'key'),
    )
    id = Column(Integer, primary_key=True)

    owner = Column(Text, nullable=False)
    key = Column(Text, nullable=False)
    value = Column(Text, nullable=False)

    def __repr__(self):
        return "Settings(id={}, owner={!r}, key={!r}, value={!r})".format(
            self.id, self.owner, self.key, self.value)

Base.metadata.create_all(engine)

def schema_updates():
    """Update the DB schema."""
    try:
        Session.execute('ALTER TABLE user_app ADD COLUMN identifier_plugin VARCHAR')
        logger.info("Added 'identifier_plugin' column to table 'user_app'")
    except OperationalError:
        logger.debug("'identifier_plugin' column already present on table 'user_app'")
    try:
        Session.execute('ALTER TABLE user_app ADD COLUMN identifier_data VARCHAR')
        logger.info("Added 'identifier_data' column to table 'user_app'")
    except OperationalError:
        logger.debug("'identifier_data' column already present on table 'user_app'")
    try:
        Session.execute('ALTER TABLE app DROP COLUMN window_text')
        logger.info("Removed 'window_text' column from table 'app'")
    except OperationalError:
        logger.debug("'window_text' column already removed from table 'app'")
    try:
        Session.execute('ALTER TABLE app DROP COLUMN use_window_text')
        logger.info("Removed 'use_window_text' column from table 'app'")
    except OperationalError:
        logger.debug("'use_window_text' column already removed from table 'app'")
    try:
        Session.execute('ALTER TABLE app DROP COLUMN default_path')
        logger.info("Removed 'default_path' column from table 'app'")
    except OperationalError:
        logger.debug("'default_path' column already removed from table 'app'")

schema_updates()

class DBConfig:
    def __init__(self, owner):
        self.owner = owner
        self.get = self.instance_get
        self.getlist = self.instance_getlist
        self.getboolean = self.instance_getboolean
        self.set = self.instance_set
        self.delete = self.instance_delete

    @staticmethod
    def static_get(owner, key, *, type=lambda x: x, fallback='NO FALLBACK'):
        value = Session.query(Settings.value).\
            filter(
                Settings.owner == owner,
                Settings.key == key).\
            order_by(Settings.id.asc()).\
            limit(1).\
            scalar()
        if value is None:
            if fallback == 'NO FALLBACK':
                raise KeyError
            else:
                return fallback
        return type(value)

    get = static_get

    def instance_get(self, key, *, type=lambda x: x, fallback='NO FALLBACK'):
        return self.static_get(self.owner, key, type=type, fallback=fallback)

    @staticmethod
    def static_getlist(owner, key, *, type=lambda x: x):
        values = Session.query(Settings.value).\
            filter(
                Settings.owner == owner,
                Settings.key == key).\
            order_by(Settings.id.asc())
        for value in values:
            try:
                yield type(value[0])
            except Exception:
                continue

    getlist = static_getlist

    def instance_getlist(self, key, *, type=lambda x: x):
        for value in self.static_getlist(self.owner, key, type=type):
            yield value

    @staticmethod
    def static_getboolean(owner, key, *, fallback='NO FALLBACK'):
        value = Session.query(Settings.value).\
            filter(
                Settings.owner == owner,
                Settings.key == key).\
            order_by(Settings.id.asc()).\
            limit(1).\
            scalar()
        if value is None:
            if fallback == 'NO FALLBACK':
                raise KeyError
            else:
                return fallback
        elif value == '1':
            return True
        elif value == '0':
            return False
        else:
            raise ValueError("{!r} is not a valid boolean value. Should be '0' or '1'.".format(value))

    getboolean = static_getboolean

    def instance_getboolean(self, key, *, fallback='NO FALLBACK'):
        return self.static_getboolean(self.owner, key, fallback=fallback)

    @staticmethod
    def static_set(owner, key, value, append=False):
        logger.debug("Setting %s.%s to %r (append=%r)", owner, key, value, append)
        settings = Session.query(Settings).\
            filter(
                Settings.owner == owner,
                Settings.key == key)
        if not append and settings.count() > 1:
            raise ValueError("Cannot replace settings list.")
        if append:
            Session.add(Settings(owner=owner, key=key, value=value))
        else:
            settings = settings.first()
            if settings:
                settings.value = value
            else:
                Session.add(Settings(owner=owner, key=key, value=value))

    set = static_set

    def instance_set(self, key, value, append=False):
        self.static_set(self.owner, key, value, append)

    @staticmethod
    def static_delete(owner, key):
        Session.query(Settings).\
            filter(
                Settings.owner == owner,
                Settings.key == key).\
            delete()

    delete = static_delete

    def instance_delete(self, key):
        self.static_delete(self.owner, key)
