"""TRUE_POSITIVE: uses yaml.load() with default Loader — CVE-2020-1747 reachable."""
import yaml
from flask import request

def parse_user_input():
    # CVE-2020-1747: default Loader can deserialize arbitrary Python objects
    payload = request.form["yaml"]
    return yaml.load(payload)

def main():
    return parse_user_input()
