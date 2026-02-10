import pytest
import os
import shutil
import tempfile
from app import app as flask_app
from pathlib import Path

@pytest.fixture
def app():
    # Setup temporary data directory
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)
    
    # Update flask app config
    flask_app.config.update({
        "TESTING": True,
    })
    
    # Override DATA_DIR and other paths in app module
    import app as app_module
    old_data_dir = app_module.DATA_DIR
    old_tools_path = app_module.TOOLS_PATH
    old_qna_path = app_module.QNA_PATH
    old_subs_path = app_module.SUBSCRIPTIONS_PATH
    old_topics_path = app_module.TOPICS_PATH

    app_module.DATA_DIR = temp_path
    app_module.TOOLS_PATH = temp_path / "tools.json"
    app_module.QNA_PATH = temp_path / "qna.json"
    app_module.SUBSCRIPTIONS_PATH = temp_path / "subscriptions.json"
    app_module.TOPICS_PATH = temp_path / "topics.json"
    
    app_module.DATA_DIR.mkdir(parents=True, exist_ok=True)

    yield flask_app

    # Teardown
    shutil.rmtree(temp_dir)
    app_module.DATA_DIR = old_data_dir
    app_module.TOOLS_PATH = old_tools_path
    app_module.QNA_PATH = old_qna_path
    app_module.SUBSCRIPTIONS_PATH = old_subs_path
    app_module.TOPICS_PATH = old_topics_path

@pytest.fixture
def client(app):
    return app.test_client()
