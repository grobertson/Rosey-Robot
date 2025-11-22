#!/usr/bin/env python3
"""Remove xfail markers from test_sprint9_integration.py"""
import re

file_path = 'tests/integration/test_sprint9_integration.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove xfail markers
pattern = r'    @pytest\.mark\.xfail\(reason="BotDatabase\.connect\(\) not implemented - temp_database fixture fails"\)\n'
new_content = re.sub(pattern, '', content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Removed xfail markers from {file_path}")
