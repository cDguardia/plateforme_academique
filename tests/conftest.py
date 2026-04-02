from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Application Flask configurée pour les tests."""
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    """Client de test Flask — nouveau client par test (isolation des cookies/sessions)."""
    return app.test_client()


@pytest.fixture(scope="session")
def runner(app):
    """CLI runner Flask."""
    return app.test_cli_runner()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Rollback après chaque test pour isoler les données."""
    with app.app_context():
        yield
        _db.session.rollback()
