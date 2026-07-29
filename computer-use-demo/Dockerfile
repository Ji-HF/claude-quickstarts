FROM docker.io/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_PRIORITY=high

RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install \
    # UI Requirements
    xvfb \
    xterm \
    xdotool \
    scrot \
    imagemagick \
    sudo \
    mutter \
    x11vnc \
    # Python/pyenv reqs
    build-essential \
    libssl-dev  \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    git \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    # Network tools
    net-tools \
    netcat \
    # PPA req
    software-properties-common && \
    # Userland apps
    sudo add-apt-repository ppa:mozillateam/ppa && \
    sudo apt-get install -y --no-install-recommends \
    libreoffice \
    firefox-esr \
    x11-apps \
    xpdf \
    gedit \
    xpaint \
    tint2 \
    galculator \
    pcmanfm \
    unzip && \
    apt-get clean

# Install noVNC (with retry and shallow clone for network resilience)
RUN git config --global http.version HTTP/1.1 && \
    git clone --depth 1 --branch v1.5.0 https://github.com/novnc/noVNC.git /opt/noVNC; \
    for i in 1 2 3; do \
        git clone --depth 1 --branch v0.12.0 https://github.com/novnc/websockify /opt/noVNC/utils/websockify && break || sleep 10; \
    done; \
    ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html

# setup user
ENV USERNAME=computeruse
ENV HOME=/home/$USERNAME
RUN useradd -m -s /bin/bash -d $HOME $USERNAME
RUN echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
USER computeruse
WORKDIR $HOME

# setup python (with retry for network resilience)
RUN for i in 1 2 3; do \
        git clone --depth 1 https://github.com/pyenv/pyenv.git ~/.pyenv && break || sleep 10; \
    done && \
    cd ~/.pyenv && src/configure && make -C src && cd .. && \
    echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc && \
    echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc
ENV PYENV_ROOT="$HOME/.pyenv"
ENV PATH="$PYENV_ROOT/bin:$PATH"
ENV PYENV_VERSION_MAJOR=3
ENV PYENV_VERSION_MINOR=11
ENV PYENV_VERSION_PATCH=6
ENV PYENV_VERSION=$PYENV_VERSION_MAJOR.$PYENV_VERSION_MINOR.$PYENV_VERSION_PATCH
RUN eval "$(pyenv init -)" && \
    pyenv install $PYENV_VERSION && \
    pyenv global $PYENV_VERSION && \
    pyenv rehash

ENV PATH="$HOME/.pyenv/shims:$HOME/.pyenv/bin:$PATH"

RUN python -m pip install --upgrade pip==23.1.2 setuptools==58.0.4 wheel==0.40.0 && \
    python -m pip config set global.disable-pip-version-check true && \
    python -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Install Python dependencies (backend replaces Streamlit)
COPY --chown=$USERNAME:$USERNAME backend/requirements.txt $HOME/backend/requirements.txt
COPY --chown=$USERNAME:$USERNAME computer_use_demo/requirements.txt $HOME/computer_use_demo/requirements.txt
RUN python -m pip install -r $HOME/backend/requirements.txt && \
    python -m pip install -r $HOME/computer_use_demo/requirements.txt

# Copy application code
COPY --chown=$USERNAME:$USERNAME image/ $HOME
COPY --chown=$USERNAME:$USERNAME computer_use_demo/ $HOME/computer_use_demo/
COPY --chown=$USERNAME:$USERNAME backend/ $HOME/backend/
COPY --chown=$USERNAME:$USERNAME static/ $HOME/static/

ARG DISPLAY_NUM=1
ARG HEIGHT=768
ARG WIDTH=1024
ENV DISPLAY_NUM=$DISPLAY_NUM
ENV HEIGHT=$HEIGHT
ENV WIDTH=$WIDTH
ENV PYTHONPATH="$HOME:$HOME/computer_use_demo:$HOME/backend"

# Expose FastAPI + noVNC ports
EXPOSE 8000 6080

# Ensure scripts are executable and have Unix line endings
RUN chmod +x $HOME/*.sh && \
    sed -i 's/\r$//' $HOME/*.sh

ENTRYPOINT ["/home/computeruse/entrypoint.sh"]
