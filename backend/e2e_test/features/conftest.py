"""Behave conftest for e2e tests."""

from behave import environment
import httpx

def before_all(context):
    """Start any shared resources."""
    context.base_url = "http://127.0.0.1:8001"
    # Create a persistent httpx client with base URL
    context.client = httpx.Client(base_url=context.base_url, timeout=30.0)

def after_all(context):
    """Cleanup."""
    context.client.close()

def background(context):
    """Ensure backend is alive - run as part of scenario."""
    try:
        r = context.client.get("/health", timeout=5)
        assert r.status_code == 200
    except Exception as e:
        raise RuntimeError(f"Backend not healthy: {e}")
