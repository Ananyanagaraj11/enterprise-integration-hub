terraform {
  required_version = ">= 1.5.0"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

# Skeleton for interview discussion — not applied against a live AWS account.
# Maps the same services as docker-compose / k8s: process-api, gateway, Spark job.

output "design" {
  value = {
    compute     = "ECS Fargate or EKS (see k8s/)"
    api_gateway = "AWS API Gateway or Kong in front of process-api"
    events      = "MSK / Kafka replacing hub/bus.py FileBus"
    data        = "RDS PostgreSQL replacing SQLite; S3 for Spark output"
    observability = "CloudWatch + OpenTelemetry /metrics scrape"
  }
}
