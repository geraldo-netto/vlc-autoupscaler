#!/usr/bin/env bash

if [[ ! ${THRESHOLD:-} =~ ^([0-9]+([.][0-9]*)?|[.][0-9]+)$ ]] ||
   ! awk -v threshold="$THRESHOLD" 'BEGIN { exit !(threshold >= 0 && threshold <= 100) }'; then
    echo 'ERROR: THRESHOLD must be a finite percentage from 0 to 100.' >&2
    exit 2
fi
