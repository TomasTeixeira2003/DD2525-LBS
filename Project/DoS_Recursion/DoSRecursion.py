import requests
import json
import time
import sys
import os
import argparse

try:
    from tqdm import tqdm
except ImportError:
    print("Install tqdm for progress bars: pip install tqdm")
    sys.exit(1)

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
except ImportError:
    print("Install colorama for colored output: pip install colorama")
    sys.exit(1)

def load_json_file(filepath):
    """Load JSON data from a file."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    with open(filepath, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            sys.exit(1)

def send_graphql_request(url, payload, idx):
    """Send a single GraphQL request and handle the response."""
    start = time.time()
    try:
        resp = requests.post(url, json=payload)
    except Exception as e:
        print(f"{Fore.RED}[Error] Query {idx+1}: Exception – {e}")
        return False, (idx+1, str(e))

    elapsed = time.time() - start
    if resp.ok:
        print(f"{Fore.GREEN}[OK]     Q{idx+1} in {elapsed:.2f}s (HTTP {resp.status_code})")
        try:
            pretty = json.dumps(resp.json(), indent=2)
            print(pretty)
        except ValueError:
            print(f"{Fore.YELLOW}[Warning] Non-JSON response: {resp.text[:200]}")
        return True, None
    else:
        print(f"{Fore.RED}[FAIL]   Q{idx+1} in {elapsed:.2f}s (HTTP {resp.status_code})")
        print(f"Response body: {resp.text[:200]}")
        return False, (idx+1, resp.status_code)

def process_requests(data, url):
    """Process a list of GraphQL requests."""
    successes = 0
    failures = []

    for idx, payload in enumerate(tqdm(data, desc="Requests")):
        success, failure_info = send_graphql_request(url, payload, idx)
        if success:
            successes += 1
        else:
            failures.append(failure_info)

    return successes, failures

def main():
    parser = argparse.ArgumentParser(
        description="GraphQL DoS-Recursion tester"
    )
    parser.add_argument(
        "--url", "-u",
        default="http://localhost:5013/graphql",
        help="GraphQL endpoint URL"
    )
    parser.add_argument(
        "--json", "-j",
        default="RecursionDVGA.json",
        help="Path to recusion-query JSON file"
    )

    args = parser.parse_args()

    # Load GraphQL request data from JSON file
    data = load_json_file(args.json)
    if isinstance(data, dict):
        data = [data]      # now it’s a list with one payload


    print(f"Sending {len(data)} GraphQL request(s) to {args.url}\n")
    successes, failures = process_requests(data, args.url)

    # Final summary
    print("\n" + "-" * 40)
    print(f"{Fore.CYAN}Summary: {successes}/{len(data)} successful, {len(failures)} failed")
    if failures:
        print(f"{Fore.RED}Failures detail: {failures}")

if __name__ == "__main__":
    main()
