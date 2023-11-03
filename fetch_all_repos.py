#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Usage:
    - Zero arguments in the root of this repo:
    fetch_all_repos.py
    as shortcut for
    fetch_all_repos.py linter_repos org.json contrib.json

    - Multiple .json files can be used:
    fetch_all_repos.py org.json contrib.json

    - To output repos to a different dir use, path as first arg:
    fetch_all_repos.py other/dest/folder/ org.json contrib.json

    - To just check repository URLs, use:
    fetch_all_repos.py --check org.json contrib.json

    Note: In case of missing URLs Exit code will be non-zero.
    This is useful for automatic tests.

"""
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
import json
import os
import shutil
import sys
import subprocess
import urllib.request

from typing import Callable, Iterator, List, Optional, TypedDict, TypeVar


T = TypeVar('T')
Url = str


class Package(TypedDict):
    name: Optional[str]
    url: Url


class Result(TypedDict, total=False):
    mode: str
    url: Url
    success: bool
    messages: List[str]


# some constants
try:
    sys.argv.remove('--check')
except ValueError:
    CHECK_MODE = False
else:
    CHECK_MODE = True

FILES = list(
    map(
        os.path.abspath,  # type: ignore[arg-type]
        [arg for arg in sys.argv if arg.endswith(".json")]
        or ['org.json', 'contrib.json'],
    )
)  # type: List[str]
DEST_DIR = os.path.abspath(
    "linter_repos"
    if not len(sys.argv) > 1 or sys.argv[1].endswith(".json")
    else sys.argv[1]
)
SL_URL = "https://github.com/SublimeLinter/SublimeLinter"

STARTUPINFO: Optional[subprocess.STARTUPINFO]
if os.name == 'nt':
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= (
        subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW
    )
    STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    STARTUPINFO = None


def ensure_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)


def url_ok(url):
    return urllib.request.urlopen(url).getcode() == 200


def execute(args: List[str], cwd: Optional[str]) -> str:
    return subprocess.check_output(
        args, cwd=cwd, startupinfo=STARTUPINFO, universal_newlines=True, encoding='utf-8'
    )


def catch_errors(fn: Callable[..., T]) -> Callable[..., T]:
    @wraps(fn)
    def wrapper(*args, package, **kwargs):
        try:
            return fn(*args, package=package, **kwargs)
        except subprocess.CalledProcessError:
            return {'mode': fn.__name__, 'url': package['url'], 'success': False}

    return wrapper


def clone_or_pull(dest: str, *, package: Package) -> Result:
    name = get_name(package)
    if os.path.exists(os.path.join(dest, name, '.git')):
        return pull(dest, package=package)
    else:
        return clone(dest, package=package)


def get_name(package: Package) -> str:
    return package['name'] or package['url'].rsplit('/')[-1]


@catch_errors
def pull(dest: str, *, package: Package) -> Result:
    url = package['url']
    cwd = os.path.join(dest, get_name(package))
    rv = execute(['git', 'pull'], cwd=cwd)
    print(url, rv.rstrip())
    return {'mode': 'pull', 'url': url, 'success': True}


@catch_errors
def clone(dest: str, *, package: Package) -> Result:
    url = package['url']
    execute(['git', 'clone', url, get_name(package)], cwd=dest)
    return {'mode': 'clone', 'url': url, 'success': True}


# @catch_errors
def check(*, package: Package) -> Result:
    url = package['url']
    try:
        execute(["git", "ls-remote", url], cwd=None)
    except subprocess.CalledProcessError as err:
        messages = [err.output]
    else:
        messages = []

    if not package['name']:
        messages += ['No package name specified']

    return {'mode': 'check', 'url': url, 'success': not messages, 'messages': messages}


def extract_urls(file: str) -> Iterator[Package]:
    with open(file, "r", encoding="utf-8") as f:
        js = json.load(f)
        packages = js["packages"]
        for p in packages:
            yield {'url': p['details'], 'name': p.get('name')}


# execution
if not CHECK_MODE:
    ensure_dir(DEST_DIR)

packages = [
    package
    for file in FILES
    for package in extract_urls(file)
    if package['url'] != SL_URL
]


removed_packages = set(os.listdir(DEST_DIR)) - {
    get_name(package) for package in packages
}
for dir in removed_packages:
    final_dir = os.path.join(DEST_DIR, dir)
    if os.path.exists(final_dir):
        print('Remove orphaned package {}'.format(final_dir))
        try:
            shutil.rmtree(os.path.join(DEST_DIR, dir))
        except Exception as err:
            print(err)

action: Callable[[Package], Result]
action = check if CHECK_MODE else partial(clone_or_pull, DEST_DIR)  # type: ignore
with ThreadPoolExecutor() as executor:
    futures = [executor.submit(action, package=package) for package in packages]

results: List[Result] = [f.result() for f in futures]


# generate report

print("\n")
print("Found {} packages".format(len(packages)))
if CHECK_MODE:
    checked = [r for r in results if r['mode'] == 'check' and r['success']]
    print("Checked {} repositories".format(len(checked)))
else:
    cloned = [r for r in results if r['mode'] == 'clone' and r['success']]
    pulled = [r for r in results if r['mode'] == 'pull' and r['success']]
    print("Cloned {} repositories".format(len(cloned)))
    print("Pulled {} repositories".format(len(pulled)))

failed = [r for r in results if not r['success']]
print(
    "{} repositories failed\n{}".format(
        len(failed),
        '\n'.join(
            "{}\n{}\n".format(
                r['url'], '\n'.join('- {}'.format(m) for m in r.get('messages', []))
            )
            for r in failed
        ),
    )
)

if failed:
    sys.exit(1)
