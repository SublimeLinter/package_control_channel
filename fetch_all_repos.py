#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    Usage:
    - Multiple .json files can be used:
    fetch_all_repos.py org.json contrib.json

    - To output repos to a different dir use, path as first arg:
    fetch_all_repos.py other/dest/folder/ org.json contrib.json

    - To just check repository URLs, use:
    fetch_all_repos.py --check org.json contrib.json

    Note: In case of missing URLs Exit code will be non-zero.
    This is useful for automatic tests.

"""
import json
import os
import shutil
import sys
import subprocess
from multiprocessing.dummy import Pool as ThreadPool
import urllib.request
from urllib.error import HTTPError

# some constants
POOL_SIZE = 10  # number of parallel threads
FILES = [arg for arg in sys.argv if arg.endswith(".json")]
DEST_DIR = "linter_repos/" if sys.argv[1].endswith(".json") else sys.argv[1]
SL_URL = "https://github.com/SublimeLinter/SublimeLinter3"
CHECK_MODE = False if "--check" not in sys.argv else True
URLS = []
MISSING_URLS = []


# function declarations
def ensure_dir(dir):
    if os.path.exists(dir):
        shutil.rmtree(dir)
    os.makedirs(dir)


def url_ok(url):
    return urllib.request.urlopen(url).getcode() == 200


def git_clone(url):
    try:
        if url_ok(url):
            dest = os.path.join(DEST_DIR, url.split("/")[-1])
            if CHECK_MODE:
                response = subprocess.check_output(["git", "ls-remote", url])
                if "Repository not found" in response:
                    raise HTTPError
            subprocess.check_output(["git", "clone", url, dest])
        else:
            raise HTTPError
    except (HTTPError, subprocess.CalledProcessError):
        MISSING_URLS.append(url)


def extract_repos(file):
    with open(file, "r", encoding="utf-8") as f:
        js = json.load(f)
        packages = js["packages"]
        for p in packages:
            URLS.append(p["details"])


# execution
if not CHECK_MODE:
    ensure_dir(DEST_DIR)

for file in FILES:
    extract_repos(file)

URLS = set(URLS)
URLS.discard(SL_URL)  # we do not want to pull SublimeLinter's repo

# threaded repo cloning
pool = ThreadPool(POOL_SIZE)
pool.map(git_clone, URLS)
pool.close()
pool.join()

# generate report
failure_count = len(MISSING_URLS)
success_count = len(URLS) - failure_count
msg_success = "\n\nCloned {} repositories.".format(success_count)
msg_failure = "Failed to clone {} repositories:\n{}".format(
    failure_count, "\n".join(MISSING_URLS))

print(msg_success)
print(msg_failure)
if MISSING_URLS:
    sys.exit(1)
