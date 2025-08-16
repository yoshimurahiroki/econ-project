# 経済学研究フルスタック（SSH/localhost前提・GPU/Quarto/RStudio 常駐）
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

# ========= 1) OS 基本 =========
RUN echo 'Acquire::Retries "10";' > /etc/apt/apt.conf.d/99-retries && \
    echo 'Acquire::http::Timeout "120";' >> /etc/apt/apt.conf.d/99-retries && \
    echo 'Acquire::https::Timeout "120";' >> /etc/apt/apt.conf.d/99-retries && \
    bash -lc 'set -e; for i in {1..5}; do \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates curl wget gnupg \
    git git-lfs make build-essential pkg-config \
    python3 \
    locales tzdata \
    # minimal TeX + Japanese support (smaller than full texlive)
    texlive-luatex \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-lang-japanese \
    texlive-bibtex-extra \
    ptex-bin \
    latexmk \
    fonts-noto-cjk fonts-noto-cjk-extra \
    openssh-client openssl \
    poppler-utils tesseract-ocr tesseract-ocr-jpn \
    sudo \
    supervisor procps \
    && break || (echo "apt failed, retry $i"; apt-get -o Acquire::Retries=3 update; sleep $((i*15))); \
    done' && \
    rm -rf /var/lib/apt/lists/*

# Node.js LTS
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# 日本語ロケール
RUN sed -i 's/^# *\(ja_JP.UTF-8 UTF-8\)/\1/' /etc/locale.gen && locale-gen
ENV LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

# ========= 2) ユーザー =========
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid "$USER_GID" "$USERNAME" || true && \
    useradd --uid "$USER_UID" --gid "$USER_GID" -m -s /bin/bash "$USERNAME" || true && \
    mkdir -p /etc/sudoers.d && \
    echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME
WORKDIR /workspaces/econ-project

# ========= 3) Miniforge (mamba) =========
ENV MAMBA_ROOT_PREFIX=/home/$USERNAME/miniforge3
RUN wget -O /tmp/miniforge.sh \
    https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh && \
    bash /tmp/miniforge.sh -b -p "$MAMBA_ROOT_PREFIX" && rm /tmp/miniforge.sh

RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && \
    conda config --remove-key channels || true && \
    conda config --remove-key default_channels || true && \
    conda config --add channels conda-forge && \
    conda config --add default_channels conda-forge && \
    conda config --set channel_priority strict && \
    conda install -n base -y mamba

RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && \
    conda config --set channel_priority strict && \
    conda config --set remote_connect_timeout_secs 60 && \
    conda config --set remote_read_timeout_secs 600 && \
    conda config --set remote_max_retries 20 && \
    conda config --set repodata_threads 1


# ========= 4) Poetry =========
ENV POETRY_VERSION=1.8.3
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/home/$USERNAME/.local/bin:$PATH"
RUN poetry config virtualenvs.create false

# ========= 5) 依存メタ（キャッシュ最適化） =========
COPY --chown=$USERNAME:$USERNAME environment.yml /tmp/environment.yml
# poetry.lock が無い環境でもビルドが落ちないように、pyproject.toml のみ確実にコピー
RUN mkdir -p /tmp/poetry
COPY --chown=$USERNAME:$USERNAME pyproject.toml /tmp/poetry/

# ========= 6) conda 環境作成 =========
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && \
    mamba env create -f /tmp/environment.yml && \
    mamba clean -a -y



ENV CONDA_DEFAULT_ENV=econ-env
ENV PATH=$MAMBA_ROOT_PREFIX/envs/econ-env/bin:$PATH

# ========= 7) Poetry 差分インストール =========
WORKDIR /tmp/poetry
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && conda activate econ-env && \
    poetry install --only dev --no-interaction --no-ansi --no-root
WORKDIR /workspaces/econ-project

# === Cleanup caches to keep image small ===
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && conda activate econ-env && \
    # clean conda/mamba caches
    conda clean -afy || true && mamba clean -a -y || true && \
    # clean pip/poetry/npm caches
    rm -rf /home/$USERNAME/.cache/pip /home/$USERNAME/.cache/pypoetry /home/$USERNAME/.npm /root/.npm || true && \
    npm cache clean --force || true && \
    # remove temporary files and apt lists
    rm -rf /tmp/* /var/tmp/* /tmp/.X11-unix || true && apt-get clean || true && rm -rf /var/lib/apt/lists/* || true



# ========= 8) Jupyter カーネル登録 (Python + R) =========
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && conda activate econ-env && \
    python -m ipykernel install --user --name econ-env --display-name "Python (econ-env)" && \
    # Register R kernel if R is present in the conda env
    if command -v R >/dev/null 2>&1; then \
    R -q -e "if (!requireNamespace('IRkernel', quietly=TRUE)) install.packages('IRkernel', repos='https://cloud.r-project.org'); IRkernel::installspec(name='ir', displayname='R (IRkernel)')" || true; \
    fi

# ========= 9) supervisor（Jupyter の自動起動） =========
USER root
RUN mkdir -p /etc/supervisor/conf.d /var/log/supervisor

# Jupyter: localhost only, token-protected (JUPYTER_TOKEN)
RUN cat >/etc/supervisor/conf.d/jupyter.conf <<'EOF'
[program:jupyter]
command=/bin/bash -lc 'exec /home/vscode/miniforge3/envs/econ-env/bin/jupyter lab --no-browser --ip=127.0.0.1 --port=8888 --ServerApp.token=${JUPYTER_TOKEN:-devtoken}'
directory=/workspaces/econ-project
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/jupyter.stdout.log
stderr_logfile=/var/log/supervisor/jupyter.stderr.log
user=vscode
stopsignal=TERM
EOF

USER $USERNAME

# ========= 10) 自動 activate =========
RUN echo "conda activate econ-env" >> /home/$USERNAME/.bashrc

# ========= 11) 前景で supervisor =========
USER root
# Keep supervisord in foreground so container stays alive; VS Code will forward ports as needed
CMD ["/usr/bin/supervisord", "-n"]
