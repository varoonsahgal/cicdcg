#!/bin/bash
# BeforeInstall hook: make sure Apache is present.
set -e
dnf install -y httpd
