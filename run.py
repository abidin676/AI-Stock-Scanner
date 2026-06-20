import subprocess
import webbrowser
import time
from pathlib import Path

print("=" * 50)
print("📈 AI Stock Scanner")
print("=" * 50)

print("\n🔍 Scanning market...\n")

result = subprocess.run(["python", "scanner.py"])

if result.returncode != 0:
    print("❌ Scanner failed")
    exit()

print("\n✅ Scan completed")

print("\n🚀 Starting Dashboard...\n")

subprocess.Popen(
    ["streamlit", "run", "dashboard.py"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

time.sleep(5)

webbrowser.open("http://localhost:8501")

print("Dashboard opened in browser.")