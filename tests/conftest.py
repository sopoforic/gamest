import os
os.environ['GAMEST_DB_PATH'] = ':memory:'

import pytest
from gamest.db import Session, Base, engine

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Session.remove()
