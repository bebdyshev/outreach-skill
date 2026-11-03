"""CLI: find a likely email for a person at a company using the configured provider."""
import argparse
import json
import sys

from providers import ProviderError, enrich


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="enrich.py", description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--person", default="", help='full name, e.g. "Jane Doe"')
    parser.add_argument("--known", default="[]",
                        help='JSON list of real addresses seen: [{"name": "...", "email": "..."}]; - reads stdin')
    args = parser.parse_args(argv)

    try:
        known = json.loads(sys.stdin.read() if args.known == "-" else args.known)
        if not (isinstance(known, list) and all(isinstance(k, dict) for k in known)):
            raise ProviderError('--known must be a JSON list of {"name", "email"} objects')
        result = enrich(args.company, args.domain, args.person, known)
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
