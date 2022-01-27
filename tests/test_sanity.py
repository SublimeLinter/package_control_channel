import json
from pathlib import Path

import pytest


@pytest.fixture
def channel():
    with open(Path("./packages.json")) as f:
        yield json.load(f)


@pytest.fixture
def repository_paths(channel):
    yield list(map(Path, channel["includes"]))


@pytest.fixture
def repositories(repository_paths):
    rv = []
    for p in repository_paths:
        with open(p) as f:
            rv.append(json.load(f))
    yield rv


def package_name(p):
    return (
        p.get("name")
        or p["details"].rsplit("/", 1)[-1]
    ).lower()


def test_sorted(repositories):
    for r_ in repositories:
        r = r_["packages"]
        assert r == sorted(r, key=package_name)
