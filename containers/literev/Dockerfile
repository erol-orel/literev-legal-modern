# ref: https://github.com/mamba-org/micromamba-docker/blob/main/Dockerfile

FROM condaforge/mambaforge:23.11.0-0

LABEL maintainer="Ivan Ogasawara <ivan.ogasawara@gmail.com>"
LABEL org.opencontainers.image.title="LiteRev"
LABEL org.opencontainers.image.authors="LiteRev Team"
LABEL org.opencontainers.image.source="https://github.com/thegraphnetwork-literev/LiteRev"
LABEL org.opencontainers.image.version="latest"
LABEL org.opencontainers.image.description="LiteRev"
LABEL org.thegraphnetwork.config.version="latest"

# it is the default, but using it here to have it explicitly
USER root

SHELL ["/bin/bash", "-c"]
# Use bash in Dockerfile RUN commands and make sure bashrc is sourced when
# executing commands with /bin/bash -c
# Needed to have the micromamba activate command configured etc.

ENV ENV_NAME=literev
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
ARG UID
ARG GID

RUN apt-get update -y \
  && apt-get install -y \
    apt-utils \
    build-essential \
    curl \
    tini \
    nginx \
    snapd \
    sudo \
    tzdata \
    gcc-multilib \
    g++-multilib \
    openssl \
  && rm -rf /var/lib/apt/lists/* \
    /var/cache/apt/archives \
    /tmp/*

RUN addgroup --gid ${GID} literev \
  && useradd --uid ${UID} --gid ${GID} -ms /bin/bash literev \
  && mkdir -p /opt/services/literev /opt/data/literev /tmp/literev \
  && chmod -R a+rwx /opt/conda /opt/services \
  && export ENV_NAME="$ENV_NAME" \
  && chown -R literev:literev /opt/services /opt/data /tmp/literev \
  && echo "literev ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/literev \
  && chmod 0440 /etc/sudoers.d/literev

USER literev

WORKDIR /opt/services/literev

COPY --chown=literev:literev ./conda/ /tmp/conda
# COPY --chown=literev:literev ./.github/workflows/.condarc /home/literev/.condarc

ARG HTTP_PROXY
ARG HTTPS_PROXY

RUN mamba env create -n $ENV_NAME --file /tmp/conda/base.yaml \
  && mamba env update -n $ENV_NAME --file /tmp/conda/service-linux-extra.yaml \
  && conda clean --all \
  && find /opt/conda/ -type f,l -name '*.pyc' -delete \
  && find /opt/conda/ -type f,l -name '*.js.map' -delete \
  && rm -rf /opt/conda/pkgs /tmp/*

ENV CONDA_PREFIX /opt/conda/envs/$ENV_NAME
ENV PATH ${CONDA_PREFIX}/bin:$PATH

# install dependencies
RUN mkdir /tmp/scripts
COPY --chown=literev:literev scripts/install-deps.sh /tmp/scripts/install-deps.sh
COPY --chown=literev:literev scripts/install-prod.sh /tmp/scripts/install-prod.sh
COPY --chown=literev:literev scripts/install-dev.sh /tmp/scripts/install-dev.sh
COPY --chown=literev:literev pyproject.toml /tmp/pyproject.toml
COPY --chown=literev:literev README.md /tmp/README.md

# create minimum structure for the installation
RUN mkdir -p /tmp/src

ARG ENV=prod

RUN /tmp/scripts/install-deps.sh

COPY --chown=literev:literev containers/literev/scripts/entrypoint.sh /opt/entrypoint.sh
COPY --chown=literev:literev src/ /opt/services/literev/src

# copy start script
COPY --chown=literev:literev containers/literev/scripts/start.sh /opt/start.sh

RUN chmod +x /opt/start.sh \
  && chmod +x /opt/entrypoint.sh \
  && echo "source /opt/entrypoint.sh" > ~/.bashrc

ARG STATIC_ROOT
ARG MEDIA_ROOT
ARG CONTAINER_VOLUME_DATA_DIR
ARG LITEREV_CACHE_DIR

ENV STATIC_ROOT ${STATIC_ROOT}
ENV MEDIA_ROOT ${MEDIA_ROOT}
ENV LITEREV_CACHE_DIR ${LITEREV_CACHE_DIR}
ENV CONTAINER_VOLUME_DATA_DIR ${CONTAINER_VOLUME_DATA_DIR}

RUN mkdir -p ${CONTAINER_VOLUME_DATA_DIR}/articles \
  && mkdir -p ${CONTAINER_VOLUME_DATA_DIR}/plot \
  && mkdir -p ${CONTAINER_VOLUME_DATA_DIR}/pkl \
  && mkdir -p ${CONTAINER_VOLUME_DATA_DIR}/static \
  && mkdir -p ${STATIC_ROOT}/.well-known/acme-challenge \
  && mkdir -p ${MEDIA_ROOT} \
  && mkdir -p ${LITEREV_CACHE_DIR}

WORKDIR /opt/services/literev/src

ENV PYTHONPATH='/opt/services/literev/src'

ENTRYPOINT ["tini", "--", "/opt/entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
