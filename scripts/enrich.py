"""CLI: find a likely email for a person at a company using the configured provider.

Input is one JSON object, inline or `-` for stdin, so web-sourced names never
go into shell arguments:
  {"company": "...", "domain": "...", "person": "First Last", "known": [{"name": "...", "email": "..."}]}
"""
import argparse
import json
import sys

from providers import ProviderError, enrich

FIELDS = {"company", "domain", "person", "known"}


def parse_request(payload: str) -> tuple:
    req = json.loads(payload)
    if not isinstance(req, dict):
        raise ProviderError("input must be a JSON object")
    unknown = set(req) - FIELDS
    if unknown:
        raise ProviderError(f"unknown fields: {', '.join(sorted(unknown))}")
    for key in ("company", "domain"):
        if not isinstance(req.get(key), str) or not req[key].strip():
            raise ProviderError(f"missing required field: {key}")
    person = req.get("person", "")
    if not isinstance(person, str):
        raise ProviderError("person must be a string")
    known = req.get("known", [])
    if not (isinstance(known, list) and all(isinstance(k, dict) for k in known)):
        raise ProviderError('known must be a JSON list of {"name", "email"} objects')
    return req["company"], req["domain"], person, known


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="enrich.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", required=True, help="request JSON object; - reads stdin")
    args = parser.parse_args(argv)

    try:
        payload = sys.stdin.read() if args.json == "-" else args.json
        result = enrich(*parse_request(payload))
    except (ProviderError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    except Exception as e:
        print(json.dumps({"error": f"provider failed: {type(e).__name__}: {e}"}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
