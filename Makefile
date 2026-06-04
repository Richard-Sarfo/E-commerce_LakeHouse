# Operations Makefile — wraps the Docker-based workflows so day-to-day tasks
# don't require remembering volume mounts or path-translation flags.
#
# Usage: `make help` lists every target. Most require a populated .env file
# (see .env.example) at the repo root.

.PHONY: help test build-test convert tf-init tf-plan tf-apply tf-destroy \
        upload trigger query check clean

SHELL  := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

# Resolve repo dir for volume mounts (works under Git Bash / MSYS on Windows
# and on native Linux/macOS).
PROJECT_DIR := $(shell pwd)
TF_IMAGE    := hashicorp/terraform:1.6
AWS_IMAGE   := amazon/aws-cli:latest
ENV_FILE    := .env

DOCKER_TF   := MSYS_NO_PATHCONV=1 docker run --rm --env-file $(ENV_FILE) -v "/$(PROJECT_DIR | sed 's|^/||'):/work" $(TF_IMAGE) -chdir=/work/terraform
DOCKER_AWS  := docker run --rm --env-file $(ENV_FILE) $(AWS_IMAGE)

help:                ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Tests ──────────────────────────────────────────────────────────────────

build-test:          ## Build the pytest Docker image
	docker build -f Dockerfile.test -t p2-test:latest .

test: build-test     ## Run the pytest suite inside the container
	docker run --rm -v "$(PROJECT_DIR):/work" -w /work --entrypoint python3 p2-test:latest -m pytest tests/ -v

# ── Local pre-flight ───────────────────────────────────────────────────────

convert:             ## Convert xlsx source files to CSV under data_csv/
	python scripts/convert_xlsx_to_csv.py

# ── Terraform ──────────────────────────────────────────────────────────────

tf-init:             ## terraform init
	$(DOCKER_TF) init

tf-plan:             ## terraform plan -out=tfplan.bin
	$(DOCKER_TF) plan -out=tfplan.bin

tf-apply:            ## terraform apply -auto-approve
	$(DOCKER_TF) apply -auto-approve

tf-destroy:          ## terraform destroy (asks for confirmation)
	$(DOCKER_TF) destroy

# ── Data ops ───────────────────────────────────────────────────────────────

BUCKET ?= $(shell $(DOCKER_TF) output -raw bucket_name 2>/dev/null)

upload:              ## Upload CSVs in data_csv/ to s3://$$BUCKET/raw/
	$(DOCKER_AWS) s3 cp /data/products.csv             s3://$(BUCKET)/raw/products/products.csv             --no-progress
	$(DOCKER_AWS) s3 cp /data/orders_apr_2025.csv      s3://$(BUCKET)/raw/orders/orders_apr_2025.csv        --no-progress
	$(DOCKER_AWS) s3 cp /data/order_items_apr_2025.csv s3://$(BUCKET)/raw/order_items/order_items_apr_2025.csv --no-progress

SFN_ARN ?= $(shell $(DOCKER_TF) output -raw state_machine_arn 2>/dev/null)

trigger:             ## Start a single Step Functions execution
	$(DOCKER_AWS) stepfunctions start-execution --state-machine-arn $(SFN_ARN) --input '{"trigger":"manual"}'

query:               ## Run the row-count sanity-check Athena query
	$(DOCKER_AWS) athena start-query-execution \
		--work-group lh-dev-lakehouse \
		--query-execution-context "Database=lh-dev_lakehouse" \
		--query-string "SELECT 'products' AS dataset, COUNT(*) AS n FROM products UNION ALL SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'order_items', COUNT(*) FROM order_items ORDER BY dataset"

# ── Lint ───────────────────────────────────────────────────────────────────

check:               ## Run ruff + terraform fmt + validate
	docker run --rm -v "$(PROJECT_DIR):/work" -w /work --entrypoint python3 p2-test:latest -m ruff check glue_jobs/ tests/ scripts/
	$(DOCKER_TF) fmt -check -recursive
	$(DOCKER_TF) validate

# ── Cleanup ────────────────────────────────────────────────────────────────

clean:               ## Remove local build artifacts
	rm -rf .pytest_cache .ruff_cache terraform/.terraform terraform/.lib.zip terraform/tfplan.bin
