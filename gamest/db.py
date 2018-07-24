import os

from sqlalchemy import Column, ForeignKey, Integer, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref, object_session
from sqlalchemy import create_engine
from sqlalchemy.sql import func

from . import DATA_DIR

Base = declarative_base()

DBPATH = os.path.join(DATA_DIR, 'gamest.db')

engine = create_engine(r'sqlite:///{}'.format(DBPATH))
Session = scoped_session(sessionmaker(bind=engine))

class App(Base):
    __tablename__ = 'app'
    id = Column(Integer, primary_key=True)

    name = Column(Text, nullable=False)
    disambiguation = Column(Text)

    window_text = Column(Text)
    use_window_text = Column(Boolean, nullable=False, default=False)

    default_path = Column(Text)

    def __repr__(self):
        return "App(id={}, name={}, disambiguation={}, window_text={}, use_window_text={})".format(
            self.id, self.name, self.disambiguation, self.window_text, self.use_window_text)

    def __str__(self):
        return self.name

    @property
    def runtime(self):
        return sum(u.runtime for u in self.user_apps)

class UserApp(Base):
    __tablename__ = 'user_app'
    id = Column(Integer, primary_key=True)

    app_id = Column(Integer, ForeignKey('app.id'), nullable=False, index=True)
    app = relationship('App', backref='user_apps')

    note = Column(Text)
    path = Column(Text, index=True)
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

Base.metadata.create_all(engine)
