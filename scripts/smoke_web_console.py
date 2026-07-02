import argparse
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROUTES = [
    "/",
    "/jobs",
    "/accounts",
    "/delivery",
    "/articles",
    "/reports",
    "/reviews",
    "/projects",
    "/quality",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the Market Info web console.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--token", default="", help="WEB_ACCESS_TOKEN value for guarded consoles.")
    parser.add_argument("--timeout", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures = []
    for route in ROUTES:
        url = urljoin(args.base_url.rstrip("/") + "/", route.lstrip("/"))
        request = Request(url)
        if args.token:
            request.add_header("Authorization", f"Bearer {args.token}")
        try:
            with urlopen(request, timeout=args.timeout) as response:
                status = response.status
                response.read()
        except HTTPError as exc:
            failures.append(f"{route}: HTTP {exc.code}")
            continue
        except URLError as exc:
            failures.append(f"{route}: {exc.reason}")
            continue

        if status != 200:
            failures.append(f"{route}: HTTP {status}")
        else:
            print(f"OK {route}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
