import requests
import json

"""
A simple script with a very basic introspections query that just checks if 
introspection is enabled or not
"""

url = "https://countries.trevorblades.com/"
introspection_query = {
    "query": """
    {
      __schema {
        queryType {
          name
        }
      }
    }
    """
}

resp = requests.post(url, json=introspection_query)

if resp.ok:
    data = resp.json()
    if "errors" in data:
        print("Introspection is disabled.")
        print(json.dumps(data["errors"], indent=2))
    elif "data" in data:
        print("Introspection is enabled.")
        print(json.dumps(data["data"], indent=2))
    else:
        print("Unexpected response.")
else:
    print(f"HTTP error: {resp.status_code}")