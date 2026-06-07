import sys
required_mods = ['tree_sitter', 'tree_sitter_c', 'chardet', 'yaml']
optional_mods = ['z3']
print('python =', sys.executable)
print('version =', sys.version.split()[0])
for m in required_mods:
    try:
        __import__(m)
        print(f'{m}: OK')
    except Exception as e:
        print(f'{m}: FAIL: {e!r}')
for m in optional_mods:
    try:
        __import__(m)
        print(f'{m}: OK (optional)')
    except Exception as e:
        print(f'{m}: SKIP optional: {e!r}')
