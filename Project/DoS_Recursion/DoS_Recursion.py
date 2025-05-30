import requests
import json
import time
import sys
import os
import argparse

try:
    from colorama import init, Fore
    init(autoreset=True)
except ImportError:
    print("Install colorama for colored output: pip install colorama")
    sys.exit(1)


def load_json_file(filepath):
    """
    Load JSON data from a file.
    """
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    with open(filepath, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            sys.exit(1)


def send_graphql_request(url, payload):
    """
    Send a GraphQL request and print the result and consumed time.
    """
    # to measure time
    start = time.time()

    # send
    try:
        resp = requests.post(url, json=payload)
    except Exception as e:
        print(f"{Fore.RED}[Error] Exception – {e}")
        return False

    elapsed = time.time() - start

    # deal with response
    if resp.ok:
        print(f"{Fore.GREEN}[OK]   Request completed in {elapsed:.2f}s (HTTP {resp.status_code})")
        try:
            print(json.dumps(resp.json(), indent=2))
        except ValueError:
            print(f"{Fore.YELLOW}[Warning] Non-JSON response: {resp.text[:200]}")
        return True
    else:
        print(f"{Fore.RED}[FAIL] HTTP {resp.status_code} in {elapsed:.2f}s")
        print(resp.text)
        return False


def main():
    parser = argparse.ArgumentParser(description="GraphQL DoS-Recursion tester")
    parser.add_argument("--url", "-u", default="http://localhost:5013/graphql",
                        help="GraphQL endpoint URL")
    parser.add_argument("--json", "-j", default="RecursionDVGA.json",
                        help="Path to recursion-query JSON file")
    args = parser.parse_args()

    # Load GraphQL request data from JSON file
    payload = load_json_file(args.json)

    # send the request
    print(f"Sending 1 GraphQL request to {args.url}\n")
    success = send_graphql_request(args.url, payload)

    # Final summary
    print("\n" + "-" * 40)
    if success:
        print(f"{Fore.CYAN}Summary: 1/1 successful")
    else:
        print(f"{Fore.RED}Summary: 0/1 successful")


if __name__ == "__main__":
    main()
