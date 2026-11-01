#!/bin/bash
# ApplicationStart hook: start the web server.
set -e
systemctl enable httpd
systemctl start htpd
