# 経済学研究環境フルスタック - mamba + Poetry + TeX + R + 日本語対応
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive


# 必要なパッケージをインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git curl wget make build-essential pkg-config \
        ca-certificates locales tzdata \
        texlive-full \
        r-base r-base-dev \
        fonts-noto-cjk fonts-noto-cjk-extra \
        openssh-client openssl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 4. nodejsインストールは元のまま
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


# ロケール（日本語も通るように）
RUN sed -i 's/^# *\(ja_JP.UTF-8 UTF-8\)/\1/' /etc/locale.gen && locale-gen
ENV LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000




# /etc/sudoers.d が存在しない場合に備えて作成
RUN mkdir -p /etc/sudoers.d && \
    groupadd --gid $USER_GID $USERNAME || true \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME || true \
    && echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# vscodeユーザーに切り替え
USER $USERNAME

# mamba（Miniforge3）インストール
ENV MAMBA_ROOT_PREFIX=/home/$USERNAME/miniforge3
SHELL ["/bin/bash", "-c"]
RUN wget -O /tmp/miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
    && bash /tmp/miniforge.sh -b -p $MAMBA_ROOT_PREFIX && rm /tmp/miniforge.sh

# Conda の初期化
RUN $MAMBA_ROOT_PREFIX/bin/conda init bash

# Poetry インストール
ENV POETRY_VERSION=1.8.3
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/home/$USERNAME/.local/bin:$PATH"

# conda 環境作成（Python/R/カーネル）
COPY --chown=$USERNAME:$USERNAME environment.yml /tmp/environment.yml
RUN . $MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh && \
    mamba env create -f /tmp/environment.yml && \
    mamba clean -a -y

# 環境をアクティブ化するためのパス設定
ENV CONDA_DEFAULT_ENV=econ-env
ENV PATH=$MAMBA_ROOT_PREFIX/envs/econ-env/bin:$PATH

# Jupyter カーネル登録（Python, R）
RUN . $MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh && \
    conda activate econ-env && \
    python -m ipykernel install --user --name econ-env --display-name "Python (econ-env)" && \
    R -q -e "install.packages('IRkernel', repos='https://cloud.r-project.org'); IRkernel::installspec(name='ir', displayname='R (IRkernel)')"


# ターミナル起動時にecon-envを自動で有効化
RUN echo "conda activate econ-env" >> /home/$USERNAME/.bashrc


# 作業ディレクトリ設定
WORKDIR /workspaces/econ-project

# デフォルトシェル
CMD ["/bin/bash"]
