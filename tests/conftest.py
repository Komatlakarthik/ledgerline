import os
from dotenv import load_dotenv
import pytest

load_dotenv()

@pytest.fixture(autouse=True, scope="session")
def configure_test_db():
    test_db = os.environ.get("TEST_DATABASE_URL")
    if test_db:
        os.environ["DATABASE_URL"] = test_db
