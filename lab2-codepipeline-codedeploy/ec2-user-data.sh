#!/bin/bash
# EC2 user data: installs the CodeDeploy agent on Amazon Linux 2023 (us-west-2).
dnf install -y ruby wget
cd /home/ec2-user
wget https://aws-codedeploy-us-west-2.s3.us-west-2.amazonaws.com/latest/install
chmod +x ./install
./install auto
systemctl enable codedeploy-agent
systemctl start codedeploy-agent
