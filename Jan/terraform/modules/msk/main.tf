# MSK (Managed Streaming for Kafka) Module

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
  description = "Subnet IDs for MSK brokers"
}

variable "security_group_id" {
  type        = string
  description = "Security group ID for MSK"
}

variable "instance_type" {
  type        = string
  default     = "kafka.m5.large"
  description = "Instance type for Kafka brokers"
}

variable "number_of_brokers" {
  type        = number
  default     = 3
  description = "Number of Kafka brokers"
}

variable "kafka_version" {
  type        = string
  default     = "3.5.1"
  description = "Kafka version"
}

variable "ebs_volume_size" {
  type        = number
  default     = 100
  description = "EBS volume size in GB per broker"
}

# MSK Configuration
resource "aws_msk_configuration" "trading" {
  name              = "trading-${var.environment}-config"
  kafka_versions    = [var.kafka_version]
  server_properties = <<PROPERTIES
auto.create.topics.enable=true
default.replication.factor=3
min.insync.replicas=2
num.partitions=6
log.retention.hours=168
log.retention.bytes=1073741824
PROPERTIES

  lifecycle {
    create_before_destroy = true
  }
}

# MSK Cluster
resource "aws_msk_cluster" "trading" {
  cluster_name           = "trading-${var.environment}"
  kafka_version          = var.kafka_version
  number_of_broker_nodes = var.number_of_brokers

  broker_node_group_info {
    instance_type   = var.instance_type
    client_subnets  = var.subnet_ids
    security_groups = [var.security_group_id]

    storage_info {
      ebs_storage_info {
        volume_size = var.ebs_volume_size
      }
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.trading.arn
    revision = aws_msk_configuration.trading.latest_revision
  }

  encryption_info {
    encryption_in_transit {
      client_broker = "TLS_PLAINTEXT"
      in_cluster    = true
    }
  }

  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }

  logging_info {
    broker_logs {
      cloudwatch_logs {
        enabled   = true
        log_group = aws_cloudwatch_log_group.msk.name
      }
    }
  }

  tags = {
    Name        = "trading-${var.environment}-msk"
    Environment = var.environment
  }
}

# CloudWatch Log Group for MSK
resource "aws_cloudwatch_log_group" "msk" {
  name              = "/aws/msk/trading-${var.environment}"
  retention_in_days = 30

  tags = {
    Environment = var.environment
  }
}

# Outputs
output "bootstrap_brokers" {
  value       = aws_msk_cluster.trading.bootstrap_brokers
  description = "Plaintext connection string for Kafka brokers"
}

output "bootstrap_brokers_tls" {
  value       = aws_msk_cluster.trading.bootstrap_brokers_tls
  description = "TLS connection string for Kafka brokers"
}

output "zookeeper_connect_string" {
  value       = aws_msk_cluster.trading.zookeeper_connect_string
  description = "Zookeeper connection string"
}

output "cluster_arn" {
  value       = aws_msk_cluster.trading.arn
  description = "MSK cluster ARN"
}
