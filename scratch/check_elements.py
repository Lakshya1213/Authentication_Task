import re
import os

app_js_path = r"D:\Task_2\app\static\js\app.js"
index_html_path = r"D:\Task_2\app\static\index.html"

# Extract all $("id") from app.js
with open(app_js_path, "r", encoding="utf-8") as f:
    js_content = f.read()

# Match patterns like: key: $("id")
pattern = r'\$\(\s*["\']([^"\']+)["\']\s*\)'
js_ids = set(re.findall(pattern, js_content))

# Extract all id="..." from index.html
with open(index_html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

# Match patterns like id="some-id" or id='some-id'
html_pattern = r'\bid\s*=\s*["\']([^"\']+)["\']'
html_ids = set(re.findall(html_pattern, html_content))

print(f"Total IDs looked up in JS: {len(js_ids)}")
print(f"Total IDs defined in HTML: {len(html_ids)}")

missing_ids = js_ids - html_ids
if missing_ids:
    print("\nWARNING: The following IDs are looked up in JS but are MISSING from HTML:")
    for mid in sorted(missing_ids):
        print(f"- {mid}")
else:
    print("\nAll JS element lookups match existing HTML IDs!")
