resource "aws_security_group" "web" {
  for_each    = local.students
  name        = "${local.prefix}-${each.key}-web-sg"
  description = "Lab 3 web server for ${each.key}: HTTP from anywhere"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.prefix}-${each.key}-web-sg", Student = each.key }
}

resource "aws_instance" "web" {
  for_each                    = local.students
  ami                         = data.aws_ssm_parameter.al2023_ami.value
  instance_type               = var.instance_type
  subnet_id                   = sort(data.aws_subnets.public.ids)[index(sort(tolist(local.students)), each.key) % length(data.aws_subnets.public.ids)]
  vpc_security_group_ids      = [aws_security_group.web[each.key].id]
  iam_instance_profile        = aws_iam_instance_profile.ec2[each.key].name
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/user_data.sh", { region = var.region })

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  # The deployment group (codedeploy.tf) looks for Name = "...-server".
  # The instance is tagged "...-web".  That mismatch is BUG 3.
  tags = {
    Name    = "${local.prefix}-${each.key}-web"
    Student = each.key
  }
}
