#!/bin/bash
# Runs in the ApplicationStart hook.
set -e
systemctl enable httpd
systemctl start httpd
