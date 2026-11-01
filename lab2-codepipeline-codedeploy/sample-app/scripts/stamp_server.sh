#!/bin/bash
# Runs in the AfterInstall hook (Lab 2, Part 10): record which server and which
# deployment produced the page you are looking at. CodeDeploy sets DEPLOYMENT_ID,
# DEPLOYMENT_GROUP_NAME, APPLICATION_NAME and LIFECYCLE_EVENT for every hook.
set -e
sed -i "s|</body>|<p class=\"stamp\">Served by $(hostname) · deployment $DEPLOYMENT_ID</p></body>|" /var/www/html/index.html
