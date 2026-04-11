output "alb_dns_name"              { value = aws_lb.main.dns_name }
output "alb_arn_suffix"            { value = aws_lb.main.arn_suffix }
output "service_security_group_id" { value = aws_security_group.ecs_service.id }
output "cluster_name"              { value = aws_ecs_cluster.main.name }
output "service_name"              { value = aws_ecs_service.api.name }
