output "app_public_ip" {
  description = "Public IP of the application (use http://<ip> to access)"
  value       = aws_eip.app.public_ip
}

output "ecr_repository_url" {
  description = "ECR repository URL for Docker images"
  value       = aws_ecr_repository.app.repository_url
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app.id
}
