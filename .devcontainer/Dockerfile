# 経済学研究フルスタック（SSH/localhost前提・GPU/Quarto/RStudio 常駐）
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

# ========= 1) OS 基本 =========
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates curl wget gnupg \
    git git-lfs make build-essential pkg-config \
    python3 \
    locales tzdata \
    texlive-full \
    fonts-noto-cjk fonts-noto-cjk-extra \
    openssh-client openssl \
    poppler-utils tesseract-ocr tesseract-ocr-jpn \
    sudo \
    gdebi-core \
    supervisor procps \
    && rm -rf /var/lib/apt/lists/*

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



# ========= 8) Jupyter/R カーネル登録 =========
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && conda activate econ-env && \
    python -m ipykernel install --user --name econ-env --display-name "Python (econ-env)" && \
    R -q -e "if (!requireNamespace('IRkernel', quietly=TRUE)) install.packages('IRkernel', repos='https://cloud.r-project.org'); IRkernel::installspec(name='ir', displayname='R (IRkernel)')"

# ========= 9) RStudio Server =========
USER root
RUN wget -O /tmp/rstudio.deb https://download2.rstudio.org/server/jammy/amd64/rstudio-server-2024.04.2-764-amd64.deb && \
    apt-get update && apt-get install -y --no-install-recommends libssl3 psmisc && \
    gdebi -n /tmp/rstudio.deb && rm -f /tmp/rstudio.deb && \
    rm -rf /var/lib/apt/lists/*
USER $USERNAME

# ========= 10) supervisor（127.0.0.1バインド & トークン付） =========
USER root
RUN mkdir -p /etc/supervisor/conf.d /etc/rstudio /var/log/supervisor

# RStudio: localhost のみ／認証は SSH 前提で off（必要時は on に調整）

RUN cat >/etc/rstudio/rserver.conf <<-'EOF'
www-address=127.0.0.1
www-port=8787
auth-none=1
EOF

# Jupyter
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


# RStudio
RUN cat >/etc/supervisor/conf.d/rstudio.conf <<'EOF'
[program:rstudio]
command=/usr/lib/rstudio-server/bin/rserver --server-user=vscode --server-daemonize=0 --server-data-dir=/var/run/rstudio-server
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/rstudio.stdout.log
stderr_logfile=/var/log/supervisor/rstudio.stderr.log
user=root
stopsignal=TERM
EOF


USER $USERNAME

# ========= 11) 自動 activate =========
RUN echo "conda activate econ-env" >> /home/$USERNAME/.bashrc

# ========= 12) 前景で supervisor =========
USER root
# SSH 前提なら EXPOSE は不要（VS Code が SSH 越しにフォワード）
CMD ["/usr/bin/supervisord", "-n"]
