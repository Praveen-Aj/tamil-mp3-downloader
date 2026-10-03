import time
import requests

eps = [
    'system/stats',
    'songs?page=1&page_size=50',
    'movies?page=1&page_size=18',
    'artists?page=1&page_size=24',
    'charts',
    'charts/chart-tamil-top-100',
    'movies/219/songs'
]

print("=== LATENCY BENCHMARK ===")
for ep in eps:
    times = []
    for _ in range(3):
        t0 = time.time()
        r = requests.get(f"http://127.0.0.1:8765/api/{ep}", timeout=5)
        times.append((time.time() - t0) * 1000)
    print(f"{ep}: avg {sum(times)/len(times):.1f} ms (min {min(times):.1f} ms, max {max(times):.1f} ms)")
