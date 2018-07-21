import os

if 'APPDATA' in os.environ.keys():
   envar = 'APPDATA'
else:
   envar = 'HOME'

DATA_DIR = os.path.join(os.environ[envar], 'gamest')
os.makedirs(DATA_DIR, exist_ok=True)
