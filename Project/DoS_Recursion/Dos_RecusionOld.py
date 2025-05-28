import requests
import json
import time
import sys

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

data = [
    #{"query":"query {\n  pastes {\n  owner  {\n  name \n}\n}\n}","variables":[]} # the middle for easier copy paste to elongate the request: {\n  name \n}
    {"query":"query {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner  {\n  pastes {\n  owner {\n  name \n} \n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}\n}","variables":[]} # the middle for easier copy paste of pastes owner: {\n  name \n}
]

url = 'http://localhost:5013/graphql'

print(f"Sending {len(data)} GraphQL request(s) to {url}\n")

successes = 0
failures = []

# Loop through each query so we can give per‐item feedback
for idx, payload in enumerate(tqdm(data, desc="Requests")):
    start = time.time()
    try:
        resp = requests.post(url, json=payload)
    except Exception as e:
        failures.append((idx+1, str(e)))
        print(f"{Fore.RED}[Error] Query {idx+1}: Exception – {e}")
        continue

    elapsed = time.time() - start
    if resp.ok:
        print(f"{Fore.GREEN}[OK]     Q{idx+1} in {elapsed:.2f}s (HTTP {resp.status_code})")
        # Pretty‑print JSON if possible
        try:
            pretty = json.dumps(resp.json(), indent=2)
            print(pretty)
        except ValueError:
            print(f"{Fore.YELLOW}[Warning] Non‑JSON response: {resp.text[:200]}")
        successes += 1
    else:
        failures.append((idx+1, resp.status_code))
        print(f"{Fore.RED}[FAIL]   Q{idx+1} in {elapsed:.2f}s (HTTP {resp.status_code})")
        print(f"Response body: {resp.text[:200]}")

# Final summary
print("\n" + "-"*40)
print(f"{Fore.CYAN}Summary: {successes}/{len(data)} successful, {len(failures)} failed")
if failures:
    print(f"{Fore.RED}Failures detail: {failures}")
