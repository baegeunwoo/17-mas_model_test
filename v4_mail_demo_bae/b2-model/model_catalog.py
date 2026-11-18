"""Candidate local models. Pure data: importable without torch or a GPU.

B2_MODEL (environment or b2-service/.env) selects the model every AI pass uses.
Without it the original Qwen3-4B setup is used, so existing installs behave as before.
Revisions are pinned; a download never follows a moving branch.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT = 'qwen3-4b'

MODELS = {
    'qwen3-4b': {
        'label': 'Qwen3-4B-Instruct-2507 · 4bit',
        'repo': 'unsloth/Qwen3-4B-Instruct-2507-bnb-4bit',
        'revision': 'f12db89cd5156e090618dded9b4367f23f8f3b33',
        'folder': 'base',
        'download_gb': 2.7,
        'vram_gb': 4,
        'hybrid_thinking': False,
        'quantize_on_load': False,
        'note': '현재 기본 모델(비교 기준)',
    },
    'qwen3-14b': {
        'label': 'Qwen3-14B · 4bit',
        'repo': 'unsloth/Qwen3-14B-bnb-4bit',
        'revision': 'b455922269e4678c84f854fe38a6993d73614a1e',
        'folder': 'qwen3-14b',
        'download_gb': 9.9,
        'vram_gb': 12,
        'hybrid_thinking': True,
        'quantize_on_load': False,
        'note': '중간 크기. 생각 모드(--think) 비교 가능',
    },
    'qwen3-32b': {
        'label': 'Qwen3-32B · 4bit',
        'repo': 'unsloth/Qwen3-32B-bnb-4bit',
        'revision': '7f721e74a6a8cc9ee352f7e49303a2c1705f9083',
        'folder': 'qwen3-32b',
        'download_gb': 19.2,
        'vram_gb': 23,
        'hybrid_thinking': True,
        'quantize_on_load': False,
        'note': 'RTX 5090(32GB)에 들어가는 가장 큰 밀집 모델. 가장 느림',
    },
    'qwen3-30b-a3b': {
        'label': 'Qwen3-30B-A3B-Instruct-2507 · 실행 시 4bit 변환',
        'repo': 'Qwen/Qwen3-30B-A3B-Instruct-2507',
        'revision': '0d7cf23991f47feeb3a57ecb4c9cee8ea4a17bfe',
        'folder': 'qwen3-30b-a3b',
        'download_gb': 61.1,
        'vram_gb': 19,
        'hybrid_thinking': False,
        # No pinned 4-bit export exists; the official weights are quantized while loading.
        'quantize_on_load': True,
        'note': 'MoE(활성 3B). 원본을 받아 불러올 때 4bit로 변환하므로 다운로드가 크고 첫 로딩이 깁니다',
    },
}
COMPARE = ('qwen3-14b', 'qwen3-32b', 'qwen3-30b-a3b')
REQUIRED_FILES = ('config.json', 'tokenizer_config.json', 'tokenizer.json')


def selected_key():
    key = os.environ.get('B2_MODEL', '').strip() or DEFAULT
    if key not in MODELS:
        raise ValueError(f'B2_MODEL={key} 은(는) 알 수 없는 모델입니다. 사용 가능: {", ".join(MODELS)}')
    return key


def spec(key=None):
    key = key or selected_key()
    return {'key': key, **MODELS[key], 'path': ROOT / 'models' / MODELS[key]['folder']}


def is_downloaded(key):
    path = spec(key)['path']
    weights = (path / 'model.safetensors').is_file() or (path / 'model.safetensors.index.json').is_file()
    return weights and all((path / name).is_file() for name in REQUIRED_FILES)
