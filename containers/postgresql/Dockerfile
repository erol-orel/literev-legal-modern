# from https://github.com/postgis/docker-postgis/blob/969ef8a9e4a22e1556ca99cab4178f6e60c1483d/14-3.2/Dockerfile
# Reference: https://github.com/thegraphnetwork/epigraphhub_py/blob/main/docker/postgresql/Dockerfile
FROM postgres:14-bullseye

ARG HOST_UID
ARG HOST_GID

ENV PGDATA /var/lib/postgresql/data


RUN usermod -u ${HOST_UID} postgres \
    && groupmod -g ${HOST_GID} postgres \
    && echo "postgres:x:${HOST_UID}:${HOST_GID}:PostgreSQL,,,:/var/lib/postgresql:/bin/bash" >> /etc/passwd

RUN install --verbose --directory --owner ${HOST_UID} --group ${HOST_GID} --mode 1777 "$PGDATA"

USER postgres
COPY ./containers/postgresql/scripts/init-database.sql /docker-entrypoint-initdb.d/init-database.sql
