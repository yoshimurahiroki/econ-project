# Economics research stack for Pixi, rv, LaTeX, Quarto, and cloud IDE agents.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-eo", "pipefail", "-c"]

# ========= 1) OS Base =========
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common gnupg ca-certificates curl wget && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    git git-lfs make build-essential pkg-config cmake default-jdk \
    libxml2-dev libxslt1-dev libffi-dev libssl-dev libcurl4-openssl-dev \
    libcairo2-dev libfontconfig1-dev libfreetype6-dev libfribidi-dev libharfbuzz-dev \
    libmagick++-dev libpng-dev libjpeg-dev libtiff-dev libwebp-dev libuv1-dev libzmq3-dev \
    libgit2-dev libglpk-dev libgmp3-dev libgsl-dev libmpfr-dev libssh-dev libssh2-1-dev \
    libabsl-dev libx11-dev libgl1-mesa-dev libglu1-mesa-dev \
    graphviz libgraphviz-dev \
    libblas-dev liblapack-dev \
    python3 python3-venv python3-pip python3-dev python3.12 python3.12-venv python3.12-dev pipx \
    locales tzdata jq golang-go bubblewrap libfuse2 libgtk-3-0 file \
    texlive-full pandoc-citeproc \
    fonts-noto-cjk fonts-noto-cjk-extra \
    openssh-client openssl \
    poppler-utils tesseract-ocr tesseract-ocr-jpn \
    sudo procps zstd unzip sqlite3 libsqlite3-dev redis-server pari-gp && \
    mkdir -p -m 755 /etc/apt/keyrings && \
    wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null && \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update && \
    apt-get install -y --no-install-recommends gh && \
    rm -rf /var/lib/apt/lists/*

# Node.js LTS
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

RUN sed -i 's/^# *\(ja_JP.UTF-8 UTF-8\)/\1/' /etc/locale.gen && locale-gen
ENV LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

# ========= 1.2) Global NPM Packages =========
# Repomix is installed globally; setup_ide_mcp.sh discovers installed MCP servers.
RUN npm install -g repomix

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
ENV PATH="/home/$USERNAME/.cargo/bin:/home/$USERNAME/.local/bin:/home/$USERNAME/go/bin:$PATH"

# Rust 1.96 supports the locked Polars MSRV (1.95) and ethnum 1.5.2.
# Rust >=1.97 changes TryFromIntError layout; update this pin with rv.lock.
# https://github.com/rust-lang/rust/issues/157363
RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs | \
    sh -s -- -y --profile minimal --default-toolchain 1.96.1

# Commit identity comes from the user's Git configuration or credential sharing.

# ========= 3) Pixi =========
RUN curl -fsSL https://pixi.sh/install.sh | bash
ENV PATH="/home/$USERNAME/.pixi/bin:$PATH"

# ========= 4) Runtime Dependency Setup =========
# The workspace .pixi volume supplies the runtime environment.
# setup-environment.sh installs project dependencies after the container starts.
RUN mkdir -p /tmp/package-lists
WORKDIR /workspaces/econ-project

# ========= 5.5) rv =========
RUN curl -sSL https://raw.githubusercontent.com/A2-ai/rv/refs/heads/main/scripts/install.sh | bash
ENV PATH="/home/$USERNAME/.local/bin:/home/$USERNAME/go/bin:$PATH"

# ========= 6) Runtime Kernel Registration =========
# The devcontainer setup script registers kernels from the workspace environment.
WORKDIR /workspaces/econ-project

# ========= 7) On-demand AI References =========
# Store task reference files in .resources.
RUN sudo mkdir -p /workspaces/econ-project/.resources && \
    sudo chown -R $USERNAME:$USERNAME /workspaces/econ-project/.resources

# ========= 8) Default Command =========
USER root
CMD ["/bin/bash"]
