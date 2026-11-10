"""Capture reproducibility metadata without recording environment variables."""
import argparse
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
from .common import utc_now


def capture():
    def command(args):
        result = subprocess.run(args, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    packages = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions() if d.metadata.get('Name'))
    report = {"captured_at": utc_now(), "python": platform.python_version(), "platform": platform.platform(),
              "git_commit": command(['git','rev-parse','HEAD']),
              "git_tracked_changes": command(['git','status','--porcelain','--untracked-files=no']),
              "installed_packages": packages}
    try:
        import torch
        report.update(torch_version=torch.__version__, cuda_version=torch.version.cuda,
                      cudnn_version=torch.backends.cudnn.version(), cuda_available=torch.cuda.is_available())
        if torch.cuda.is_available():
            report['gpu_name'] = torch.cuda.get_device_name(0)
            report['gpu_memory_bytes'] = torch.cuda.get_device_properties(0).total_memory
            report['nvidia_driver'] = command(['nvidia-smi','--query-gpu=driver_version','--format=csv,noheader'])
    except ImportError:
        report['torch_version'] = None
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        parser.error('Provenance already exists; preserve it and choose a new file for another runtime')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(capture(),indent=2)+'\n')
    print(f'Saved runtime provenance to {path}')


if __name__=='__main__':
    main()
