#!/bin/bash

if [[ -z "$1" ]]; then
    echo "Syntax: $0 <key> <runtests.py parameters>"
    exit 1
fi

key=$1
echo "${*:2}"

ssh-agent
ssh-add $key
./runtests.py $*
