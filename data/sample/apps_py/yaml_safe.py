"""FALSE_POSITIVE: uses pyyaml but only safe_load — CVE-2020-1747 is unreachable."""
import yaml

def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)

def write_config(path, cfg):
    with open(path, "w") as f:
        yaml.safe_dump(cfg, f)

def main():
    cfg = load_config("config.yaml")
    write_config("out.yaml", cfg)
