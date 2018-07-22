import os

import appdirs

DATA_DIR = appdirs.user_data_dir('gamest', False)
LOG_DIR = appdirs.user_log_dir('gamest', False)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
