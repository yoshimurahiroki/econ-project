FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# システム依存パッケージ
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    git curl wget make build-essential pkg-config \
    ca-certificates sudo locales tzdata \
    texlive-full \
    r-base r-base-dev \
    nodejs npm \
    fonts-noto-cjk fonts-noto-cjk-extra \
  && rm -rf /var/lib/apt/lists/*

# 日本語ロケール
RUN sed -i 's/^# *ja_JP.UTF-8/ja_JP.UTF-8/' /etc/locale.gen && locale-gen
ENV LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

# Mamba (Mambaforge) インストール
ENV MAMBA_ROOT_PREFIX=/opt/conda
SHELL ["/bin/bash", "-lc"]
RUN curl -L -o mambaforge.sh \
      https://github.com/conda-forge/miniforge/releases/latest/download/Mambaforge-Linux-x86_64.sh \
    && bash mambaforge.sh -b -p $MAMBA_ROOT_PREFIX \
    && rm mambaforge.sh \
    && echo ". $MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" >> /etc/skel/.bashrc

# Poetry インストール
ENV POETRY_VERSION=1.8.3
RUN curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION
ENV PATH="/root/.local/bin:$PATH"

# Conda 環境作成
COPY environment.yml /tmp/environment.yml
RUN mamba env create -f /tmp/environment.yml && mamba clean -a -y
ENV CONDA_DEFAULT_ENV=dev
ENV PATH=$MAMBA_ROOT_PREFIX/envs/dev/bin:$PATH

# Jupyter カーネル登録
RUN python -m ipykernel install --name dev --display-name "Python (dev)"
RUN R -q -e "install.packages('IRkernel', repos='https://cloud.r-project.org'); IRkernel::installspec(name='ir', displayname='R (IRkernel)')"

WORKDIR /workspaces
