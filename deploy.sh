#!/bin/sh -x
set -e

# My FAAS is arm64, so need to install this to cross-compile
docker run --rm --privileged \
  multiarch/qemu-user-static \
  --reset -p yes

# Build and deploy
faas-cli template store pull python3-flask
faas-cli publish -f nombres.yml --platforms linux/arm64 --build-arg 'TEST_ENABLED=false'
faas-cli deploy -f nombres.yml
