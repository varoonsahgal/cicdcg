#!/bin/bash
# Runs in the BeforeInstall hook: make sure the web server is installed.
set -e
dnf install -y httpd
