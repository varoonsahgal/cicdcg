variable "region" {
  description = "AWS region for all lab resources."
  type        = string
  default     = "us-west-2"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used to run Terraform (instructor)."
  type        = string
  default     = "instructor-01"
}

variable "student_count" {
  description = "How many student environments to create (participant-01 .. participant-NN)."
  type        = number
  default     = 15
}

variable "student_prefix" {
  description = "Prefix of the students' IAM user names; also used in every resource name."
  type        = string
  default     = "participant"
}

variable "instance_type" {
  description = "EC2 instance type for each student's web server."
  type        = string
  default     = "t3.micro"
}
