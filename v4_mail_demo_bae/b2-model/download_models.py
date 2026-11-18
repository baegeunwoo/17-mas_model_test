"""Download only pinned public model assets. Does not send meeting data.

No arguments: the default analysis model and the search model (unchanged behaviour).
--compare: the RTX 5090 comparison candidates in model_catalog.COMPARE.
--model a,b: specific candidates.
"""
from pathlib import Path
import argparse, os, shutil, sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import model_catalog

SEARCH_MODEL = ('intfloat/multilingual-e5-small', '614241f622f53c4eeff9890bdc4f31cfecc418b3', 'multilingual-e5-small')
PATTERNS = ['*.json', '*.safetensors', '*.txt', '*.model', '*.jinja', 'README.md', 'LICENSE*']


def fetch(repo, revision, folder):
    from huggingface_hub import snapshot_download
    print('Downloading', repo, revision, flush=True)
    snapshot_download(repo_id=repo, revision=revision, local_dir=ROOT / 'models' / folder, token=False, allow_patterns=PATTERNS)


def main():
    parser = argparse.ArgumentParser(description='Download pinned local models.')
    parser.add_argument('--model', default='', help='comma-separated keys: ' + ', '.join(model_catalog.MODELS))
    parser.add_argument('--compare', action='store_true', help='download every comparison candidate')
    parser.add_argument('--yes', action='store_true', help='skip the size confirmation')
    args = parser.parse_args()
    # runtime.py deliberately enforces offline inference. Downloads are an explicit separate step.
    for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
        os.environ.pop(key, None)
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    if not args.model and not args.compare:
        default = model_catalog.MODELS[model_catalog.DEFAULT]
        for repo, revision, folder in ((default['repo'], default['revision'], default['folder']), SEARCH_MODEL):
            fetch(repo, revision, folder)
        print('Both model downloads completed. Run 05 to check GPU and files.')
        return
    keys = list(model_catalog.COMPARE) if args.compare else [k.strip() for k in args.model.split(',') if k.strip()]
    unknown = [k for k in keys if k not in model_catalog.MODELS]
    if unknown:
        raise SystemExit('Unknown model: ' + ', '.join(unknown) + ' / available: ' + ', '.join(model_catalog.MODELS))
    pending = [k for k in keys if not model_catalog.is_downloaded(k)]
    for key in keys:
        if key not in pending:
            print('Already present:', key, flush=True)
    if not pending:
        print('Nothing to download.')
        return
    need = sum(model_catalog.MODELS[k]['download_gb'] for k in pending)
    (ROOT / 'models').mkdir(exist_ok=True)
    free = shutil.disk_usage(ROOT / 'models').free / 1e9
    for key in pending:
        m = model_catalog.MODELS[key]
        print(f"  {key}: {m['label']} - about {m['download_gb']} GB, needs about {m['vram_gb']} GB GPU memory", flush=True)
    print(f'Total about {need:.1f} GB. Free disk space: {free:.1f} GB.', flush=True)
    if free < need + 5:
        raise SystemExit('Not enough disk space. Free some space or choose fewer models with --model.')
    if not args.yes and input('Continue? (Y/N) ').strip().lower() not in ('y', 'yes'):
        raise SystemExit('Cancelled.')
    for key in pending:
        m = model_catalog.MODELS[key]
        fetch(m['repo'], m['revision'], m['folder'])
    print('Downloads completed. Run 07 to compare topic grouping.')


if __name__ == '__main__':
    main()
