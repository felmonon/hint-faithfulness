#!/usr/bin/env bash
# Colab driver for the v2 run. Usage (from /content/hf):
#   bash scripts/colab_v2.sh setup|sync|phase1|phase2|phase3
# Every long step runs in the background and logs to colab_logs/<step>.log.
set -u
cd /content/hf
mkdir -p colab_logs
case "$1" in
  setup)
    python -c "import sklearn" 2>/dev/null || pip install -q scikit-learn > colab_logs/pip.log 2>&1
    python -c "import torch, transformers, sklearn; print(torch.__version__, transformers.__version__, sklearn.__version__)" >> colab_logs/pip.log 2>&1 \
      && echo SETUP_DONE >> colab_logs/pip.log ;;
  after1)
    # Wait for Phase 1, then run the GPU parts of Phase 2 and all of Phase 3.
    until grep -q "PHASE1_DONE\|PHASE1_FAILED" colab_logs/phase1.log 2>/dev/null; do sleep 30; done
    grep -q PHASE1_DONE colab_logs/phase1.log || exit 1
    bash scripts/colab_v2.sh phase2
    bash scripts/colab_v2.sh phase3 ;;
  pack)
    # Bundle logs and v2 artifacts for a browser download (transport only).
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    name=${2:-run}; name=${name//[^A-Za-z0-9._-]/_}
    tar -czf "/content/v2-${name}-${stamp}.tar.gz" -- colab_logs artifacts/v2
    sha256sum -- "/content/v2-${name}-${stamp}.tar.gz" ;;
  status)
    nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader
    for f in colab_logs/*.log; do echo "== $f"; tail -c 600 "$f"; echo; done
    wc -l artifacts/v2/*/*.jsonl 2>/dev/null ;;
  phase1)
    python -m src.gen_v2 --output artifacts/v2/phase1/responses.jsonl > colab_logs/phase1.log 2>&1 \
      && echo PHASE1_DONE >> colab_logs/phase1.log || echo PHASE1_FAILED >> colab_logs/phase1.log ;;
  phase2)
    { python -m src.phase2_v2 early && python -m src.phase2_v2 acts; } > colab_logs/phase2.log 2>&1 \
      && echo PHASE2_DONE >> colab_logs/phase2.log || echo PHASE2_FAILED >> colab_logs/phase2.log ;;
  phase3)
    ( for s in acts vectors check steer; do VLLM_ENABLE_V1_MULTIPROCESSING=0 python -m src.phase3_v2 $s || exit 1; done ) > colab_logs/phase3.log 2>&1 \
      && echo PHASE3_DONE >> colab_logs/phase3.log || echo PHASE3_FAILED >> colab_logs/phase3.log ;;
esac
