# from https://github.com/postgis/docker-postgis/blob/969ef8a9e4a22e1556ca99cab4178f6e60c1483d/14-3.2/Dockerfile
# Reference: https://github.com/thegraphnetwork/epigraphhub_py/blob/main/docker/postgresql/Dockerfile
FROM postgres:12-bullseye

USER postgres
COPY ./containers/postgresql/scripts/init-database.sql /docker-entrypoint-initdb.d/init-database.sql
