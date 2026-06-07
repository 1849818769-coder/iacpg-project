import sys
mods = ['tree_sitter', 'tree_sitter_c', 'chardet', 'yaml', 'z3']
print('python =', sys.executable)
print('version =', sys.version.split()[0])
for m in mods:
    try:
        __import__(m)
        print(f'{m}: OK')
    except Exception as e:
        print(f'{m}: FAIL: {e!r}')
