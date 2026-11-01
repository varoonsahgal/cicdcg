#!/bin/bash
# ApplicationStop hook: stop the web server (ignore errors if it is not running yet).
systemctl stop httpd || true
