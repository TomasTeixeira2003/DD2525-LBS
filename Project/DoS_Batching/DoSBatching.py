#!/usr/bin/env python3
import argparse
import json
import sys
import time

import requests
from tqdm import tqdm
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


def load_introspection_query(path: str) -> dict:
    """
    Load the JSON file containing the introspection query payload (each GraphQL Project needs their own personalized query).
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print("\n" + Fore.RED + f"Error loading introspection query from {path}: {e}\n")
        sys.exit(1)


def load_schema_file(path: str) -> dict:
    """
    Load a pre-fetched GraphQL introspection schema result (JSON) 
    (if such a thing is given e.g. when introspection is disabled and we get the sche,a through other sources).
    """
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print("\n" + Fore.RED + f"Error loading schema from {path}: {e}\n")
        sys.exit(1)


def send_query(url: str, payload) -> tuple:
    """
    Sends a POST to the GraphQL endpoint and measures the response time.
    Returns (response, elapsed_time), or (None, -1) in case of exception.
    """
    try:
        start = time.time()
        resp = requests.post(url, json=payload)
        # display errors
        """try:
            message = resp.json()
            print(resp.status_code, message['errors'][0]['message'])
        except Exception as e:
            print("No error occured in the response of the POST")"""
        return resp, time.time() - start
    except Exception as e:
        print("\n" + Fore.RED + f"[Exception] {e}\n")
        return None, -1


def extract_query_fields(schema: dict) -> list:
    """
    Returns a list of tuples (field_name, subfields).
    If the field returns an object/interface/union, subfields=['__typename'], else [] (otherwise we get errors of missing subfields).
    """
    fields = []
    types = schema.get("data", {}).get("__schema", {}).get("types", [])
    # build a map for type lookup -- not needed anymore
    # type_map = {t.get("name"): t for t in types}

    query_type = next((t for t in types if t.get("name") == "Query"), None)
    if not query_type:
        return []

    for f in query_type.get("fields", []):
        field_name = f.get("name")
        type_info = f.get("type")
        # unwrap NON_NULL and LIST
        while type_info.get("ofType"):
            type_info = type_info["ofType"]
        kind = type_info.get("kind")
        # for OBJECT, INTERFACE, UNION use __typename
        if kind in ("OBJECT", "INTERFACE", "UNION"):
            subfields = ["__typename"]
        else:
            subfields = []
        fields.append((field_name, subfields))
    return fields


def measure_field_timings(url: str, fields: list) -> list:
    """
    Name says it all, it measures and saves the time for each query build 
    from the schema we got through the introspection (or the provided schema).
    Returns a list of (field_name, subfields, elapsed_time).
    """
    timings = []
    for field, subfields in tqdm(fields, desc="Measuring fields"):
        selection = f"{{ {field} {{ {' '.join(subfields)} }} }}" if subfields else f"{{ {field} }}"
        payload = {"query": f"query {selection}"}
        resp, elapsed = send_query(url, payload)
        if resp and resp.ok:
            timings.append((field, subfields, elapsed))
        else:
            print(Fore.YELLOW + f"[Warning] {field} -> HTTP {resp.status_code if resp else 'Error'}")
    return sorted(timings, key=lambda x: x[2], reverse=True)


def send_batched_queries(url: str, field: str, batch_size: int, subfield: str = None) -> None:
    if subfield:
        query_string = f"query {{ {field} {{ {subfield} }} }}"
    else:
        query_string = f"query {{ {field} }}"
    batch = [{"query": query_string} for _ in range(batch_size)]
    resp, elapsed = send_query(url, batch)
    if resp and resp.ok:
        print("\n" + Fore.GREEN + f"[OK] Batch of {batch_size} completed in {elapsed:.2f}s\n")
    else:
        print(Fore.RED + f"[FAIL] HTTP {resp.status_code} in {elapsed:.2f}s")
        print(resp.text)


def main():
    # 1) Parser so that the script doesn't need to be changed each time
    #    takes a url, an introspection query or schema and a number for how many queries should be in the batching
    parser = argparse.ArgumentParser(description="GraphQL DoS-batching fuzz tester")
    parser.add_argument("--url", "-u", default="http://localhost:1337/graphql", help="GraphQL endpoint URL")
    parser.add_argument("--introspect", "-i", default="introspecQuery.json", help="Introspection query file")
    parser.add_argument("--schema", "-s", default=None, help="Schema file (skip introspection)")
    parser.add_argument("--batch", "-b", type=int, default=3, help="Batch size")
    args = parser.parse_args()

    # Load the schema (if provided) or fetch the schema through an introspection query
    if args.schema: # load
        print("\n Loading schema from file… \n")
        schema = load_schema_file(args.schema)
        print("\n" + Fore.GREEN + f"Schema loaded from {args.schema}\n")
    else: # fetch
        # 1) Load introspection file & send query
        introspection_payload = load_introspection_query(args.introspect)
        print("\nRunning introspection… \n")
        resp, elapsed = send_query(args.url, introspection_payload)
        if resp is None or not resp.ok:
            code = resp.status_code if resp else "N/A"
            print("\n" + Fore.RED + f"Introspection failed (HTTP {code}). Exiting.\n")
            sys.exit(1)
        print("\n" + Fore.GREEN + f"Introspection OK ({elapsed:.2f}s)\n")
        schema = resp.json()

    # Extract all possible fields from schema to be able to build as many requests as possible
    # Then send the queries to the graphql endpoint to check that they are 
    fields = extract_query_fields(schema)
    if not fields:
        print("\n")
        print(Fore.RED + "No query fields found.")
        print("\n")
        sys.exit(1)
    print("\n" + Fore.CYAN + f"Found {len(fields)} top-level query fields.\n")

    # Measure timings of each possible query
    timings = measure_field_timings(args.url, fields)
    if not timings:
        print("\n" + Fore.RED + "No successful field timings.\n")
        sys.exit(1)

    slowest_field, subfields, slowest_time = timings[0]
    print("\n" + Fore.GREEN + f"Slowest field: {slowest_field} ({slowest_time:.2f}s)\n")
    subfield = subfields[0] if subfields else None
    # send batch query    
    send_batched_queries(args.url, slowest_field, args.batch, subfield)

if __name__ == "__main__":
    main()
