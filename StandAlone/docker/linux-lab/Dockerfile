FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    coreutils \
    grep \
    sed \
    gawk \
    findutils \
    less \
    vim-tiny \
    tree \
    jq \
    curl \
    wget \
    net-tools \
    iputils-ping \
    dnsutils \
    procps \
    strace \
    lsof \
    iproute2 \
    man-db \
    bash-completion \
    bc \
    && rm -rf /var/lib/apt/lists/*

COPY data/ /data/
COPY exercises/ /exercises/

RUN chmod 644 /data/* && chmod 755 /exercises/*

WORKDIR /data

CMD ["sleep", "infinity"]
