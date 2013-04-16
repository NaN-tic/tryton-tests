#!/bin/bash

if [[ -z "$1" ]]; then
    echo "Syntax: $0 directory"
    exit 1
fi

main=$1
echo "<html>"
echo "<head></head>"
echo "<body>"
echo "<table><tr><th>Module</th><th>Output</th></tr>"
for dir in `ls -1 $main`; do
    full=$main$dir
    output=$(pyflakes $full 2>/dev/null | grep -v __init__.py:)
    if [[ -z "$output" ]]; then
        color="green"
    else
        color="red"
    fi
    url=$(cat $full/.hg/hgrc 2>/dev/null | grep -v paths | cut -d ' ' -f 3)
    echo "<tr>"
    echo "<td style='border-bottom-style: solid; border-bottom-width: 1px; background-color: $color'>$dir</td>"
    echo "<td style='border-bottom-style: solid; border-bottom-width: 1px; background-color: $color'><pre>$output</pre></td>"
    echo "<td style='border-bottom-style: solid; border-bottom-width: 1px; background-color: $color'>$url</td>"
    echo "</tr>"
done
echo "</table>"
echo "</body>"
