TERRAFORM := terraform -chdir=factory/terraform
REPO := victormasson21/software-factory

.PHONY: up down

up:
	$(TERRAFORM) init
	$(TERRAFORM) apply
	factory/bootstrap.sh "$$($(TERRAFORM) output -raw ipv4)" $(REPO)

down:
	$(TERRAFORM) destroy
