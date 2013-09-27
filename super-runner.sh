#!/bin/bash

export PATH="/usr/local/bin:$PATH"

if [[ -z "$1" ]]; then
    echo "Syntax: $0 <key> <runtests.py parameters>"
    exit 1
fi

key=$1
echo "${*:2}"

ssh-agent /bin/bash -c "ssh-add $key && ./runtests.py $*"

# Remove postgresql test databases
psql -l | grep test_ | cut -d " " -f 2 | awk '{system("dropdb "$1)}'
