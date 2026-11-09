"""All tests use disposable SQLite, even when local production config exists."""
import os
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import pytest


@pytest.fixture(autouse=True)
def isolated_database(monkeypatch, tmp_path):
    # Import first: common loads config once. Override it for every test afterward.
    import pipeline.db
    from pipeline.publish import youtube
    monkeypatch.setattr(youtube, "_auth_failed", set())
    monkeypatch.setenv('DB_BACKEND', 'sqlite')
    monkeypatch.setattr(pipeline.db, 'DATA_DIR', tmp_path)
    import os
    for name in list(os.environ):
        if name in ('SUPABASE_SERVICE_KEY','ANTHROPIC_API_KEY','YT_CLIENT_SECRET','GH_TOKEN','GITHUB_TOKEN') or name.startswith(('YT_REFRESH_TOKEN','IG_ACCESS_TOKEN','META_ACCESS_TOKEN')):
            monkeypatch.delenv(name, raising=False)

    import requests
    import httpx
    import subprocess
    original_run = subprocess.run
    def offline(*args, **kwargs):
        raise AssertionError('External network access is disabled in tests')
    def local_process(args, *other, **kwargs):
        if isinstance(args, (list, tuple)) and str(args[0]).split('/')[-1] in ('gh','curl','wget'):
            raise AssertionError('External CLI access is disabled in tests')
        return original_run(args, *other, **kwargs)
    monkeypatch.setattr(requests.sessions.Session, 'request', offline)
    monkeypatch.setattr(httpx.Client, 'send', offline)
    monkeypatch.setattr(subprocess, 'run', local_process)
