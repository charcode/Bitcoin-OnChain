FROM ubuntu:24.04

ARG FULCRUM_VERSION=1.12.0
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tar zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/fulcrum

RUN curl -fsSL \
      "https://github.com/cculianu/Fulcrum/releases/download/v${FULCRUM_VERSION}/Fulcrum-${FULCRUM_VERSION}-x86_64-linux.tar.gz" \
      -o /tmp/fulcrum.tar.gz \
    && tar -xzf /tmp/fulcrum.tar.gz --strip-components=1 -C /opt/fulcrum \
    && rm /tmp/fulcrum.tar.gz \
    && chmod +x /opt/fulcrum/Fulcrum

VOLUME ["/data/fulcrum"]
EXPOSE 50001 50002

ENTRYPOINT ["/opt/fulcrum/Fulcrum"]
CMD ["/etc/fulcrum/fulcrum.conf"]
