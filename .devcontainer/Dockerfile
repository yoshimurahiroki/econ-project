# Economics Research Full Stack (SSH/localhost, GPU/Quarto/RStudio ready)
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]

# ========= 1) OS Base =========
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates curl wget gnupg \
    git git-lfs make build-essential pkg-config \
    python3 python3-venv python3-pip python3-dev \
    locales tzdata \
    texlive-full \
    fonts-noto-cjk fonts-noto-cjk-extra \
    openssh-client openssl \
    poppler-utils tesseract-ocr tesseract-ocr-jpn \
    sudo procps \
    && rm -rf /var/lib/apt/lists/*

# Node.js LTS
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN sed -i 's/^# *\(ja_JP.UTF-8 UTF-8\)/\1/' /etc/locale.gen && locale-gen
ENV LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

# ========= 2) User Setup =========
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

# ========= 5) Dependency Metadata (cache optimization) =========
COPY --chown=$USERNAME:$USERNAME environment.yml /tmp/environment.yml
# Copy only pyproject.toml to ensure build succeeds even without poetry.lock
RUN mkdir -p /tmp/poetry
COPY --chown=$USERNAME:$USERNAME pyproject.toml /tmp/poetry/

# ========= 6) Conda Environment Creation =========
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && \
    mamba env create -f /tmp/environment.yml && \
    mamba clean -a -y

ENV CONDA_DEFAULT_ENV=econ-env
ENV PATH=$MAMBA_ROOT_PREFIX/envs/econ-env/bin:$PATH

# ========= 8) Poetry Differential Install =========
WORKDIR /tmp/poetry
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && conda activate econ-env && \
    poetry install --only dev --no-interaction --no-ansi --no-root
WORKDIR /workspaces/econ-project

# ========= 9) Jupyter/R Kernel Registration =========
RUN . "$MAMBA_ROOT_PREFIX/etc/profile.d/conda.sh" && conda activate econ-env && \
    python -m ipykernel install --user --name econ-env --display-name "Python (econ-env)" && \
    R -q -e "if (!requireNamespace('IRkernel', quietly=TRUE)) install.packages('IRkernel', repos='https://cloud.r-project.org'); IRkernel::installspec(name='ir', displayname='R (IRkernel)')"

# ========= 10) Auto Activate =========
RUN echo "conda activate econ-env" >> /home/$USERNAME/.bashrc

# ========= 11) Default Command =========
USER root
CMD ["/bin/bash"]
