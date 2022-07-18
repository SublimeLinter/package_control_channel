from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys


from typing import Dict, List, Optional


DEST_DIR = os.path.abspath(
    "linter_repos"
    if not len(sys.argv) > 1 or sys.argv[1].endswith(".json")
    else sys.argv[1]
)
STARTUPINFO: Optional[subprocess.STARTUPINFO]
if os.name == 'nt':
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= (
        subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW
    )
    STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    STARTUPINFO = None


def execute(args: List[str], cwd: Optional[str]) -> str:
    return subprocess.check_output(
        args,
        cwd=cwd,
        startupinfo=STARTUPINFO,
        universal_newlines=True,
        encoding='utf-8',
        stderr=subprocess.PIPE,
    )


def describe_head(root: str, name: str) -> Dict[str, str]:
    path = os.path.join(root, name)
    try:
        tag = execute(['git', 'describe', '--exact-match', '--tags'], cwd=path).strip()
    except subprocess.CalledProcessError:
        return {'name': name}
    return {'name': name, 'tag': tag}


with ThreadPoolExecutor() as executor:
    futures = [
        executor.submit(describe_head, DEST_DIR, name)
        for name in set(os.listdir(DEST_DIR))
    ]

results = [f.result() for f in futures]
results = sorted(results, key=lambda r: r['name'])

for r in results:
    if 'tag' in r:
        print('{}  {}'.format(r['name'], r['tag']))

print('\n\n')
for r in results:
    if 'tag' not in r:
        print('{}  release pending'.format(r['name']))
