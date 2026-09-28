# Hugging Face Spaces (Docker SDK) - backend only. The frontend deploys separately on Vercel.
# Free CPU tier gives 16GB RAM, vs. Render's free-tier 512MB, which torch+chromadb+sentence-transformers
# don't fit in (see DEPLOY.md for that story). No changes to the retrieval stack itself - same
# chromadb + sentence-transformers + rank_bm25 as local dev, just given enough room to run.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Spaces containers run as uid 1000 - see https://huggingface.co/docs/hub/spaces-sdks-docker
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

RUN pip install --no-cache-dir --upgrade pip

COPY --chown=user requirements.txt .
# torch is a transitive dep of sentence-transformers - PyPI's default wheel bundles the full CUDA/GPU
# stack (nvidia-cudnn, nvidia-cublas, etc, well over 1GB), which every host we run on (Render/Railway
# free tiers, HF Spaces CPU basic) has no GPU to use anyway. Installing the CPU-only build first means
# the later `-r requirements.txt` install already finds torch satisfied and never pulls the GPU one in.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user app app
COPY --chown=user scripts scripts
COPY --chown=user data/synthetic data/synthetic

# INDEX_DATA_URL is a public GitHub Release URL (not sensitive) - set as a Space "Variable" so HF
# passes it in as a build-arg (see app/tools/build_index.py / scripts/fetch_index_data.py for what
# it downloads and why). Baked in at build time so restarts don't re-download it.
ARG INDEX_DATA_URL
ENV INDEX_DATA_URL=$INDEX_DATA_URL
RUN python scripts/fetch_index_data.py

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
