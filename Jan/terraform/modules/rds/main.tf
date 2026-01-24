# RDS PostgreSQL with TimescaleDB Module

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for RDS"
}

variable "security_group_id" {
  type        = string
  description = "Security group ID for RDS"
}

variable "instance_class" {
  type        = string
  default     = "db.r6g.large"
  description = "RDS instance class"
}

variable "allocated_storage" {
  type        = number
  default     = 100
  description = "Allocated storage in GB"
}

variable "db_name" {
  type        = string
  default     = "trades"
  description = "Database name"
}

variable "db_username" {
  type        = string
  default     = "trading"
  description = "Database username"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Database password"
}

variable "multi_az" {
  type        = bool
  default     = true
  description = "Enable Multi-AZ deployment"
}

# DB Subnet Group
resource "aws_db_subnet_group" "trading" {
  name       = "trading-${var.environment}"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "trading-${var.environment}-db-subnet"
    Environment = var.environment
  }
}

# DB Parameter Group for TimescaleDB
resource "aws_db_parameter_group" "timescale" {
  name   = "trading-${var.environment}-timescale"
  family = "postgres16"

  parameter {
    name  = "shared_preload_libraries"
    value = "timescaledb"
  }

  parameter {
    name  = "max_connections"
    value = "200"
  }

  parameter {
    name  = "work_mem"
    value = "65536"  # 64MB
  }

  parameter {
    name  = "maintenance_work_mem"
    value = "524288"  # 512MB
  }

  tags = {
    Environment = var.environment
  }
}

# RDS Instance
resource "aws_db_instance" "trading" {
  identifier = "trading-${var.environment}"

  engine            = "postgres"
  engine_version    = "16.1"
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.trading.name
  vpc_security_group_ids = [var.security_group_id]
  parameter_group_name   = aws_db_parameter_group.timescale.name

  multi_az                  = var.multi_az
  publicly_accessible       = false
  backup_retention_period   = 7
  backup_window             = "03:00-04:00"
  maintenance_window        = "Mon:04:00-Mon:05:00"
  auto_minor_version_upgrade = true
  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "trading-${var.environment}-final" : null

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = {
    Name        = "trading-${var.environment}-db"
    Environment = var.environment
  }
}

# Outputs
output "endpoint" {
  value       = aws_db_instance.trading.endpoint
  description = "RDS endpoint"
}

output "address" {
  value       = aws_db_instance.trading.address
  description = "RDS address (hostname)"
}

output "port" {
  value       = aws_db_instance.trading.port
  description = "RDS port"
}

output "database_name" {
  value       = aws_db_instance.trading.db_name
  description = "Database name"
}

output "connection_string" {
  value       = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.trading.endpoint}/${var.db_name}"
  sensitive   = true
  description = "Full connection string"
}
