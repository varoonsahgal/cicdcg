#!/bin/bash
# Runs in the ApplicationStop hook (before the new version is installed).
# "|| true" so a stopped/not-yet-installed server does not fail the deployment.
systemctl stop httpd || true
