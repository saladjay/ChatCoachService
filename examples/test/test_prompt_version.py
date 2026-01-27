"""Test prompt version extraction and removal."""

from app.services.prompt_utils import extract_prompt_version, add_prompt_version

# Test 1: Extract version from prompt
test_prompt = "[PROMPT:test_v1]\nThis is a test prompt"
version, clean = extract_prompt_version(test_prompt)
print(f"Test 1 - Extract version:")
print(f"  Original: {repr(test_prompt)}")
print(f"  Version: {version}")
print(f"  Clean: {repr(clean)}")
print()

# Test 2: No version in prompt
test_prompt2 = "This is a prompt without version"
version2, clean2 = extract_prompt_version(test_prompt2)
print(f"Test 2 - No version:")
print(f"  Original: {repr(test_prompt2)}")
print(f"  Version: {version2}")
print(f"  Clean: {repr(clean2)}")
print()

# Test 3: Add version to prompt
test_prompt3 = "This is a new prompt"
with_version = add_prompt_version(test_prompt3, "my_version_v1")
print(f"Test 3 - Add version:")
print(f"  Original: {repr(test_prompt3)}")
print(f"  With version: {repr(with_version)}")
print()

# Test 4: Extract from added version
version4, clean4 = extract_prompt_version(with_version)
print(f"Test 4 - Extract from added:")
print(f"  Version: {version4}")
print(f"  Clean: {repr(clean4)}")
print(f"  Match original: {clean4 == test_prompt3}")
