import logging
import os
from logging.handlers import TimedRotatingFileHandler
from shutil import copyfile

import appdirs
import pkg_resources

DATA_DIR = appdirs.user_data_dir('gamest', False)
LOG_DIR = appdirs.user_log_dir('gamest', False)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)-15s %(levelname)-8s %(name)s: %(message)s')
LOG_FILE = os.path.join(LOG_DIR, 'gamest.log')

handler = TimedRotatingFileHandler(LOG_FILE, when='midnight')
handler.setFormatter(logging.Formatter('%(asctime)-15s %(levelname)-8s %(name)s: %(message)s'))
logger.addHandler(handler)
