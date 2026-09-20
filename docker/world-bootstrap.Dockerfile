FROM mysql:8.4

USER root
RUN microdnf install -y python3.12 \
  && microdnf clean all

COPY bootstrap-world.sh /usr/local/bin/bootstrap-world
RUN chmod 755 /usr/local/bin/bootstrap-world

ENTRYPOINT ["/usr/local/bin/bootstrap-world"]
