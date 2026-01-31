# Dev Environment - Main Terraform Configuration
# Ties together all modules for the development environment

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment for remote state (recommended for team use)
  # backend "s3" {
  #   bucket         = "trading-terraform-state"
  #   key            = "dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "energy-trading"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Variables
variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Environment name"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Database password"
}

variable "ecr_repository_url" {
  type        = string
  description = "ECR repository URL for Docker images"
}

# Networking Module
module "networking" {
  source = "../../modules/networking"

  environment        = var.environment
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
}

# MSK (Kafka) Module
module "msk" {
  source = "../../modules/msk"

  environment       = var.environment
  vpc_id            = module.networking.vpc_id
  subnet_ids        = module.networking.private_subnet_ids
  security_group_id = module.networking.msk_security_group_id

  # Dev sizing (smaller for cost)
  instance_type     = "kafka.m5.large"
  number_of_brokers = 3
  ebs_volume_size   = 100
}

# RDS Module
module "rds" {
  source = "../../modules/rds"

  environment       = var.environment
  vpc_id            = module.networking.vpc_id
  subnet_ids        = module.networking.private_subnet_ids
  security_group_id = module.networking.rds_security_group_id

  # Dev sizing
  instance_class    = "db.r6g.large"
  allocated_storage = 100
  multi_az          = false  # Single AZ for dev

  db_name     = "trades"
  db_username = "trading"
  db_password = var.db_password
}

# ECS Module
module "ecs" {
  source = "../../modules/ecs"

  environment           = var.environment
  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  private_subnet_ids    = module.networking.private_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  ecs_security_group_id = module.networking.ecs_security_group_id

  kafka_bootstrap_servers = module.msk.bootstrap_brokers
  postgres_dsn            = module.rds.connection_string
  ecr_repository_url      = var.ecr_repository_url

  # Dev sizing
  api_cpu            = 512
  api_memory         = 1024
  api_desired_count  = 2
  consumer_cpu       = 512
  consumer_memory    = 1024
  consumer_desired_count = 2
}

# Outputs
output "vpc_id" {
  value       = module.networking.vpc_id
  description = "VPC ID"
}

output "kafka_bootstrap_servers" {
  value       = module.msk.bootstrap_brokers
  description = "Kafka bootstrap servers"
}

output "rds_endpoint" {
  value       = module.rds.endpoint
  description = "RDS endpoint"
}

output "api_url" {
  value       = "http://${module.ecs.alb_dns_name}"
  description = "API URL"
}

output "ecs_cluster_arn" {
  value       = module.ecs.cluster_arn
  description = "ECS cluster ARN"
}
