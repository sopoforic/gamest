import json
from unittest.mock import MagicMock, patch

import pytest

from gamest import db
from gamest_plugins.process_identifier.module import ProcessIdentifierPlugin


def make_proc(name, username='testuser', exe='/usr/bin/game', cmdline=None, create_time=0.0):
    p = MagicMock()
    cmdline = cmdline if cmdline is not None else []
    p.info = {
        'name': name,
        'username': username,
        'exe': exe,
        'cmdline': cmdline,
        'create_time': create_time,
    }
    p.username.return_value = username
    p.exe.return_value = exe
    p.cmdline.return_value = cmdline
    p.create_time.return_value = create_time
    return p


@pytest.fixture
def plugin(mock_application):
    with patch('getpass.getuser', return_value='testuser'):
        return ProcessIdentifierPlugin(mock_application)


def test_candidates_filters_trash_names(plugin):
    procs = [make_proc('steam'), make_proc('mygame')]
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=procs):
        result = plugin.candidates()
    assert all(ua.note != 'steam' for ua in result)
    assert any(ua.note == 'mygame' for ua in result)

def test_candidates_filters_trash_regex(plugin):
    procs = [make_proc('gnome-shell'), make_proc('mygame')]
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=procs):
        result = plugin.candidates()
    assert all(ua.note != 'gnome-shell' for ua in result)
    assert any(ua.note == 'mygame' for ua in result)

def test_candidates_filters_by_username(plugin):
    procs = [make_proc('mygame', username='otheruser'), make_proc('yourgame', username='testuser')]
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=procs):
        result = plugin.candidates()
    assert all(ua.note != 'mygame' for ua in result)
    assert any(ua.note == 'yourgame' for ua in result)

def test_candidates_identifier_data_shape(plugin):
    procs = [make_proc('mygame', exe='/usr/bin/mygame', cmdline=['/usr/bin/mygame', '--arg'])]
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=procs):
        result = plugin.candidates()
    assert len(result) == 1
    ua = result[0]
    assert ua.note == 'mygame'
    assert ua.identifier_plugin == 'ProcessIdentifierPlugin'
    data = json.loads(ua.identifier_data)
    assert data['exe'] == '/usr/bin/mygame'
    assert '/usr/bin/mygame' in data['cmdline']

def test_candidates_sorted_by_create_time_descending(plugin):
    procs = [
        make_proc('alpha', create_time=1.0),
        make_proc('beta', create_time=3.0),
        make_proc('gamma', create_time=2.0),
    ]
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=procs):
        result = plugin.candidates()
    assert [ua.note for ua in result] == ['beta', 'gamma', 'alpha']


def _register_user_app(exe, cmdline=None):
    app = db.App(name='Registered Game')
    db.Session.add(app)
    db.Session.flush()
    ua = db.UserApp(
        app=app,
        identifier_plugin='ProcessIdentifierPlugin',
        identifier_data=json.dumps({'exe': exe, 'cmdline': cmdline or ''}),
    )
    db.Session.add(ua)
    db.Session.commit()
    return ua


def test_identify_game_matching_exe(plugin):
    ua = _register_user_app('/usr/bin/mygame')
    plugin.clear_cache()
    proc = make_proc('mygame', exe='/usr/bin/mygame')
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=[proc]):
        result = plugin.identify_game()
    assert result is not None
    assert result[1].id == ua.id

def test_identify_game_cmdline_matches(plugin):
    ua = _register_user_app('/usr/bin/game', cmdline='/usr/bin/game --mode=1')
    plugin.clear_cache()
    proc = make_proc('game', exe='/usr/bin/game', cmdline=['/usr/bin/game', '--mode=1'])
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=[proc]):
        result = plugin.identify_game()
    assert result is not None
    assert result[1].id == ua.id

def test_identify_game_cmdline_mismatch(plugin):
    _register_user_app('/usr/bin/game', cmdline='/usr/bin/game --mode=1')
    plugin.clear_cache()
    proc = make_proc('game', exe='/usr/bin/game', cmdline=['/usr/bin/game', '--mode=2'])
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=[proc]):
        result = plugin.identify_game()
    assert result is None

def test_identify_game_no_match(plugin):
    _register_user_app('/usr/bin/mygame')
    plugin.clear_cache()
    proc = make_proc('other', exe='/usr/bin/other')
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter', return_value=[proc]):
        result = plugin.identify_game()
    assert result is None

def test_identify_game_picks_oldest(plugin):
    _register_user_app('/usr/bin/mygame')
    plugin.clear_cache()
    old_proc = make_proc('mygame', exe='/usr/bin/mygame', create_time=1.0)
    new_proc = make_proc('mygame', exe='/usr/bin/mygame', create_time=5.0)
    with patch('gamest_plugins.process_identifier.module.psutil.process_iter',
               return_value=[new_proc, old_proc]):
        result = plugin.identify_game()
    assert result is not None
    assert result[0].info['create_time'] == 1.0
