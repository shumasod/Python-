variable "project_name"        { type = string }
variable "aws_region"          { type = string }
variable "vpc_id"              { type = string }
variable "public_subnet_ids"   { type = list(string) }
variable "private_subnet_ids"  { type = list(string) }
variable "ecr_repository_url"  { type = string }
variable "image_tag"           { type = string; default = "latest" }
variable "cpu"                 { type = number; default = 512 }
variable "memory"              { type = number; default = 1024 }
variable "desired_count"       { type = number; default = 2 }
variable "task_role_arn"       { type = string }
variable "execution_role_arn"  { type = string }
variable "log_group_name"      { type = string }
variable "db_host"             { type = string; sensitive = true }
variable "db_name"             { type = string }
variable "db_username"         { type = string; sensitive = true }
variable "db_password"         { type = string; sensitive = true }
variable "s3_bucket_name"      { type = string }
