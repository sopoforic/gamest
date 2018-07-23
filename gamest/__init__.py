import configparser
import logging
import os
import pkg_resources
from logging.handlers import TimedRotatingFileHandler
from shutil import copyfile

import appdirs

DATA_DIR = appdirs.user_data_dir('gamest', False)
LOG_DIR = appdirs.user_log_dir('gamest', False)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

config = configparser.ConfigParser(delimiters=('=',))
config.optionxform = lambda o: o
config.read_dict({ 'options' : { 'visible_only' : 'True',
                                      'debug' : 'False' } })

CONFIG_PATH = os.path.join(DATA_DIR, 'gamest.conf')
config.read([CONFIG_PATH])
if not os.path.exists(CONFIG_PATH):
    copyfile(pkg_resources.resource_filename('gamest', 'gamest.conf.default'), CONFIG_PATH)

if config['options'].getboolean('debug'):
    level = logging.DEBUG
else:
    level = logging.INFO

logger = logging.getLogger(__name__)
logging.basicConfig(level=level,
            format='%(asctime)-15s %(levelname)-8s %(name)s: %(message)s')
LOG_FILE = os.path.join(LOG_DIR, 'gamest.log')

handler = TimedRotatingFileHandler(LOG_FILE, when='midnight')
handler.setFormatter(logging.Formatter('%(asctime)-15s %(levelname)-8s %(name)s: %(message)s'))
logger.addHandler(handler)
