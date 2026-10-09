import re
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.config import HTTP_TIMEOUT, HTTP_MAX_RETRIES, HTTP_BACKOFF_FACTOR, COTRIP_API_KEY

logger = logging.getLogger(__name__)

_KEY_PATTERN = re.compile(re.escape(COTRIP_API_KEY)) if COTRIP_API_KEY else None


def redact_key(text: str) -> str:
    if _KEY_PATTERN and COTRIP_API_KEY:
        return _KEY_PATTERN.sub("***", text)
    return text


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=HTTP_MAX_RETRIES,
        backoff_factor=HTTP_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get(url: str, session: requests.Session = None, **kwargs) -> requests.Response:
    s = session or make_session()
    safe_url = redact_key(url)
    logger.debug("GET %s", safe_url)
    try:
        resp = s.get(url, timeout=HTTP_TIMEOUT, **kwargs)
        logger.debug("GET %s -> %d (%d bytes)", safe_url, resp.status_code, len(resp.content))
        return resp
    except requests.RequestException as exc:
        logger.error("GET %s failed: %s", safe_url, redact_key(str(exc)))
        raise
