FROM mysql@sha256:3466ba4a4828aa8d46fb7c3bc16b67b781c98413cf4ea0fac6feaa6e881faa26 AS mysql_client

FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential ccache libtool cmake-data ninja-build cmake clang libclang-rt-18-dev \
       git ca-certificates curl unzip python3 default-mysql-client openssl lua5.1 \
       default-libmysqlclient-dev libboost-all-dev libssl-dev libmysql++-dev \
       libreadline-dev zlib1g-dev libbz2-dev libncurses-dev liblzma-dev \
    && rm -rf /var/lib/apt/lists/*

# Native world bootstrap requires --no-login-paths, which Ubuntu's 8.0 client lacks.
# Retain the build-time client development libraries and use the pinned 8.4 CLI.
COPY --from=mysql_client /usr/bin/mysql /usr/bin/mysql
RUN mysql --no-defaults --no-login-paths --help >/dev/null

ENV LUA51=/usr/bin/lua5.1
WORKDIR /g1/source
ENTRYPOINT ["python3", "-B", "/g1/control/g1-container.py"]
