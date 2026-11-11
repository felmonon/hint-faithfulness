#!/usr/bin/env bash
# Colab driver for the v2 run. Usage (from /content/hf):
#   bash scripts/colab_v2.sh setup|sync|phase1|phase2|phase3
# Every long step runs in the background and logs to colab_logs/<step>.log.
set -u
cd /content/hf
mkdir -p colab_logs
case "$1" in
  setup)
    pip install -q vllm==0.8.5.post1 scikit-learn > colab_logs/pip.log 2>&1
    python -c "import vllm, torch, transformers; print(vllm.__version__, torch.__version__, transformers.__version__)" >> colab_logs/pip.log 2>&1
    echo SETUP_DONE >> colab_logs/pip.log ;;
  pack)
    # Bundle logs and v2 artifacts for a browser download (transport only).
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    tar czf /content/v2-$2-$stamp.tar.gz colab_logs artifacts/v2
    sha256sum /content/v2-$2-$stamp.tar.gz ;;
  status)
    nvidia-smi --query-gpu=name,utilization.gpu,memory.used --format=csv,noheader
    for f in colab_logs/*.log; do echo "== $f"; tail -c 600 "$f"; echo; done
    wc -l artifacts/v2/*/*.jsonl 2>/dev/null ;;
  phase1)
    VLLM_USE_V1=0 python -m src.gen_v2 --output artifacts/v2/phase1/responses.jsonl > colab_logs/phase1.log 2>&1
    echo PHASE1_DONE >> colab_logs/phase1.log ;;
  phase2)
    python -m src.phase2_v2 all > colab_logs/phase2.log 2>&1
    echo PHASE2_DONE >> colab_logs/phase2.log ;;
  phase3)
    VLLM_USE_V1=0 python -m src.phase3_v2 all > colab_logs/phase3.log 2>&1
    echo PHASE3_DONE >> colab_logs/phase3.log ;;
esac
