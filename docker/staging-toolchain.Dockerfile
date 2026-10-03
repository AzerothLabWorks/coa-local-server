FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ccache libtool cmake-data ninja-build cmake clang \
        git ca-certificates curl unzip python3 default-mysql-client openssl \
        default-libmysqlclient-dev libboost-all-dev libssl-dev libmysql++-dev \
        libreadline-dev zlib1g-dev libbz2-dev libncurses-dev liblzma-dev \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update \
    && apt-get install -y --no-install-recommends libclang-rt-18-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CCACHE_DIR=/ccache
ENV CCACHE_MAXSIZE=2G
ENV CCACHE_COMPILERCHECK=content
ENV CCACHE_CPP2=true

WORKDIR /candidate

CMD ["python3", "-B", "tools/verify_all.py", "--stages", "source,build,unit", "--jobs", "2"]
