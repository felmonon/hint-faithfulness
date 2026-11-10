"""Read-only checks. Reports whether a key exists without exposing its value."""
import argparse
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", action="store_true", help="Check public OpenRouter models/pricing without making inference calls")
    parser.add_argument("--output", help="Optional JSON report")
    args = parser.parse_args()
    report = {"python": sys.version.split()[0], "platform": platform.platform(),
              "openrouter_key_configured": bool(os.environ.get("OPENROUTER_API_KEY")), "packages": {}}
    for package in ["torch", "transformers", "datasets", "numpy", "scikit-learn", "matplotlib", "huggingface-hub"]:
        try:
            report["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report["packages"][package] = None
    try:
        import torch
        report["cuda_available"] = torch.cuda.is_available()
        report["mps_available"] = torch.backends.mps.is_available()
    except ImportError:
        report["cuda_available"] = report["mps_available"] = False
    if args.catalog:
        from .providers import OpenRouterClient
        requested = {"qwen/qwen3-1.7b", "qwen/qwen3-4b", "deepseek/deepseek-r1-0528", "qwen/qwen3-235b-a22b-thinking-2507",
                     "qwen/qwen3-30b-a3b-instruct-2507"}
        report["model_catalog"] = [{k: m.get(k) for k in ["id", "pricing", "supported_parameters", "context_length"]}
                                   for m in OpenRouterClient.models() if m["id"] in requested]
        report["catalog_missing"] = sorted(requested - {m["id"] for m in report["model_catalog"]})
    print(json.dumps(report, indent=2))
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
