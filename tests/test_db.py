import pytest
from gamest.db import Session, DBConfig, App, UserApp, PlaySession, Settings


def test_get_existing_key():
    Session.add(Settings(owner='owner', key='k', value='v'))
    assert DBConfig.static_get('owner', 'k') == 'v'

def test_get_fallback():
    assert DBConfig.static_get('owner', 'missing', fallback='default') == 'default'

def test_get_no_fallback_raises():
    with pytest.raises(KeyError):
        DBConfig.static_get('owner', 'missing')

def test_get_type_conversion():
    Session.add(Settings(owner='owner', key='k', value='42'))
    assert DBConfig.static_get('owner', 'k', type=int) == 42


def test_getboolean_true():
    Session.add(Settings(owner='owner', key='k', value='1'))
    assert DBConfig.static_getboolean('owner', 'k') is True

def test_getboolean_false():
    Session.add(Settings(owner='owner', key='k', value='0'))
    assert DBConfig.static_getboolean('owner', 'k') is False

def test_getboolean_invalid_raises():
    Session.add(Settings(owner='owner', key='k', value='yes'))
    with pytest.raises(ValueError):
        DBConfig.static_getboolean('owner', 'k')

def test_getboolean_missing_with_fallback():
    assert DBConfig.static_getboolean('owner', 'missing', fallback=True) is True

def test_getboolean_missing_no_fallback_raises():
    with pytest.raises(KeyError):
        DBConfig.static_getboolean('owner', 'missing')


def test_getlist_multiple_values():
    for v in ['a', 'b', 'c']:
        Session.add(Settings(owner='owner', key='k', value=v))
    assert list(DBConfig.static_getlist('owner', 'k')) == ['a', 'b', 'c']

def test_getlist_empty():
    assert list(DBConfig.static_getlist('owner', 'missing')) == []


def test_set_new_key():
    DBConfig.static_set('owner', 'k', 'v')
    assert DBConfig.static_get('owner', 'k') == 'v'

def test_set_updates_existing():
    Session.add(Settings(owner='owner', key='k', value='old'))
    DBConfig.static_set('owner', 'k', 'new')
    assert DBConfig.static_get('owner', 'k') == 'new'

def test_set_append_adds_row():
    Session.add(Settings(owner='owner', key='k', value='first'))
    DBConfig.static_set('owner', 'k', 'second', append=True)
    assert list(DBConfig.static_getlist('owner', 'k')) == ['first', 'second']

def test_set_replace_multivalue_raises():
    Session.add(Settings(owner='owner', key='k', value='a'))
    Session.add(Settings(owner='owner', key='k', value='b'))
    with pytest.raises(ValueError):
        DBConfig.static_set('owner', 'k', 'new')


def test_delete_removes_key():
    Session.add(Settings(owner='owner', key='k', value='v'))
    DBConfig.static_delete('owner', 'k')
    with pytest.raises(KeyError):
        DBConfig.static_get('owner', 'k')

def test_delete_nonexistent_no_error():
    DBConfig.static_delete('owner', 'missing')


def test_instance_get_delegates():
    Session.add(Settings(owner='MyOwner', key='k', value='v'))
    cfg = DBConfig('MyOwner')
    assert cfg.get('k') == DBConfig.static_get('MyOwner', 'k')


def _make_user_app(initial_runtime=0):
    app = App(name='Test Game')
    Session.add(app)
    Session.flush()
    ua = UserApp(app=app, initial_runtime=initial_runtime)
    Session.add(ua)
    Session.flush()
    return ua


def test_runtime_no_sessions():
    ua = _make_user_app(initial_runtime=500)
    assert ua.runtime == 500

def test_runtime_with_sessions():
    ua = _make_user_app(initial_runtime=100)
    Session.add(PlaySession(user_app=ua, duration=200))
    Session.add(PlaySession(user_app=ua, duration=300))
    Session.commit()
    assert ua.runtime == 600

def test_runtime_initial_zero_one_session():
    ua = _make_user_app(initial_runtime=0)
    Session.add(PlaySession(user_app=ua, duration=120))
    Session.commit()
    assert ua.runtime == 120


def test_app_runtime_sums_user_apps():
    app = App(name='Game')
    Session.add(app)
    Session.flush()
    ua1 = UserApp(app=app, initial_runtime=0)
    ua2 = UserApp(app=app, initial_runtime=0)
    Session.add(ua1)
    Session.add(ua2)
    Session.flush()
    Session.add(PlaySession(user_app=ua1, duration=60))
    Session.add(PlaySession(user_app=ua2, duration=40))
    Session.commit()
    assert app.runtime == 100
