variable "project_name"         { type = string }
variable "vpc_id"               { type = string }
variable "private_subnet_ids"   { type = list(string) }
variable "db_instance_class"    { type = string }
variable "db_name"              { type = string }
variable "db_username"          { type = string; sensitive = true }
variable "db_password"          { type = string; sensitive = true }
variable "db_allocated_storage" { type = number }
variable "ecs_sg_id"            { type = string }
variable "multi_az"             { type = bool; default = true }
variable "deletion_protection"  { type = bool; default = true }
