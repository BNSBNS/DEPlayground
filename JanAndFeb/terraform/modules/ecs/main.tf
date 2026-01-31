# ECS Fargate Module for API, Consumer, Producer

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for ALB"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for ECS tasks"
}

variable "alb_security_group_id" {
  type        = string
  description = "Security group ID for ALB"
}

variable "ecs_security_group_id" {
  type        = string
  description = "Security group ID for ECS tasks"
}

variable "kafka_bootstrap_servers" {
  type        = string
  description = "Kafka bootstrap servers"
}

variable "postgres_dsn" {
  type        = string
  sensitive   = true
  description = "PostgreSQL connection string"
}

variable "ecr_repository_url" {
  type        = string
  description = "ECR repository URL for images"
}

variable "api_cpu" {
  type        = number
  default     = 1024
  description = "API task CPU units"
}

variable "api_memory" {
  type        = number
  default     = 2048
  description = "API task memory in MB"
}

variable "api_desired_count" {
  type        = number
  default     = 2
  description = "Desired number of API tasks"
}

variable "consumer_cpu" {
  type        = number
  default     = 1024
  description = "Consumer task CPU units"
}

variable "consumer_memory" {
  type        = number
  default     = 2048
  description = "Consumer task memory in MB"
}

variable "consumer_desired_count" {
  type        = number
  default     = 3
  description = "Desired number of consumer tasks"
}

# ECS Cluster
resource "aws_ecs_cluster" "trading" {
  name = "trading-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Environment = var.environment
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/trading-${var.environment}/api"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "consumer" {
  name              = "/ecs/trading-${var.environment}/consumer"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "producer" {
  name              = "/ecs/trading-${var.environment}/producer"
  retention_in_days = 30
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_execution" {
  name = "trading-${var.environment}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Tasks
resource "aws_iam_role" "ecs_task" {
  name = "trading-${var.environment}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# ALB
resource "aws_lb" "api" {
  name               = "trading-${var.environment}-api"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  tags = {
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "api" {
  name        = "trading-${var.environment}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# API Task Definition
resource "aws_ecs_task_definition" "api" {
  family                   = "trading-${var.environment}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "api"
    image = "${var.ecr_repository_url}:api-latest"

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "KAFKA_BOOTSTRAP_SERVERS", value = var.kafka_bootstrap_servers },
      { name = "POSTGRES_DSN", value = var.postgres_dsn },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "ENVIRONMENT", value = var.environment }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "api"
      }
    }

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# Consumer Task Definition
resource "aws_ecs_task_definition" "consumer" {
  family                   = "trading-${var.environment}-consumer"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.consumer_cpu
  memory                   = var.consumer_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "consumer"
    image = "${var.ecr_repository_url}:consumer-latest"

    environment = [
      { name = "KAFKA_BOOTSTRAP_SERVERS", value = var.kafka_bootstrap_servers },
      { name = "POSTGRES_DSN", value = var.postgres_dsn },
      { name = "KAFKA_CONSUMER_GROUP", value = "trade-aggregator" },
      { name = "WINDOW_DURATION_SECONDS", value = "60" },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "ENVIRONMENT", value = var.environment }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.consumer.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "consumer"
      }
    }
  }])
}

# API Service
resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.trading.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.api]
}

# Consumer Service
resource "aws_ecs_service" "consumer" {
  name            = "consumer"
  cluster         = aws_ecs_cluster.trading.id
  task_definition = aws_ecs_task_definition.consumer.arn
  desired_count   = var.consumer_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }
}

# Data source for current region
data "aws_region" "current" {}

# Outputs
output "cluster_arn" {
  value = aws_ecs_cluster.trading.arn
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "consumer_service_name" {
  value = aws_ecs_service.consumer.name
}

output "alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "alb_arn" {
  value = aws_lb.api.arn
}
