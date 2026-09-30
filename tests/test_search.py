"""Day 5 test: Send 5 tender-specific queries to POST /search and display results."""
import urllib.request
import json


def search(query: str, top_k: int = 5):
    """Sends a query to the /search endpoint and returns the parsed JSON response."""
    payload = json.dumps({"query": query, "top_k": top_k}).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:8000/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    response = urllib.request.urlopen(req)
    return json.loads(response.read())


# --- 5 tender-specific test queries ---
test_queries = [
    "What is the minimum annual turnover required?",
    "What experience is required for bidders?",
    "What is the EMD or Earnest Money Deposit amount?",
    "What documents are required for submission?",
    "What is the bid validity period?",
]

print("=" * 70)
print("  TENDER-AI SEARCH TEST — Day 5")
print("=" * 70)

for i, query in enumerate(test_queries, start=1):
    print(f"\n{'─' * 60}")
    print(f"  Query {i}: {query}")
    print(f"{'─' * 60}")

    try:
        result = search(query, top_k=3)
        print(f"  Results found: {result['results_count']}")

        for j, r in enumerate(result["results"], start=1):
            print(f"\n  📄 Result {j}  (score: {r['score']})")
            print(f"     Page: {r['metadata'].get('page', '?')}")
            # Show first 200 chars of the chunk text
            preview = r["text"][:200].replace("\n", " ").strip()
            print(f"     Text: {preview}...")

    except Exception as e:
        print(f"  ❌ ERROR: {e}")

print(f"\n{'=' * 70}")
print("  TEST COMPLETE")
print(f"{'=' * 70}")
