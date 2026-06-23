from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


IDENTITY_QUERY_KEYS = {"__biz", "mid", "idx", "sn"}


def normalize_article_url(url: str) -> str:
    stripped_url = url.strip()
    if not stripped_url:
        raise ValueError("url is required")

    parsed = urlsplit(stripped_url)
    identity_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key in IDENTITY_QUERY_KEYS
    ]
    identity_params.sort(key=lambda item: item[0])

    query = urlencode(identity_params) if identity_params else ""
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            query,
            "",
        )
    )


def hash_content(text: str) -> str:
    return sha256(text.strip().encode("utf-8")).hexdigest()
