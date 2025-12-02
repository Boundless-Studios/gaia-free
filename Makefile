KEY_FILE := ~/.config/sops/age/keys.txt
# Override these with your own values: make add-admin ADMIN_EMAIL=you@example.com
ADMIN_EMAIL ?= admin@example.com
ADMIN_NAME ?= Local Admin

OS := $(shell uname -s)
UNAME_M := $(shell uname -m)
DETACH :=

# If SERVICES is specified, only that SERVICES will be built and started.
# Useful for isolated development/testing.
SERVICES ?=
DETACH :=

ifeq ($(UNAME_M),x86_64)
  ARCH := amd64
else ifeq ($(UNAME_M),arm64)
  ARCH := arm64
else
  ARCH := unknown
endif

COMPOSE_FILES = -f docker-compose.yml

ifeq ($(OS),Windows_NT)
  COMPOSE_FILES += -f docker-compose.windows.yaml
endif

ifeq ($(GITHUB_ACTIONS),true)
  COMPOSE_FILES += -f docker-compose.ci.yaml
endif

.PHONY: prerequisites
prerequisites: ## check prerequisites for the project
	@python3 -V
	node -v
	@docker -v
	@uv -V
	age --version


.PHONY: init
init: ## initialize the environment
	mkdir -p $(dir $(KEY_FILE))
	@echo =================== give the public key to Gaia admin ======================
	@if [ ! -f $(KEY_FILE) ]; then \
		age-keygen -o $(KEY_FILE); \
	else \
  		grep '# public key:' $(KEY_FILE); \
	fi
	uv sync


.PHONY: build
build: ## build docker images
	cp $(KEY_FILE) secrets/age-key.txt
	docker compose --profile dev $(COMPOSE_FILES) build --build-arg ARCH=$(ARCH) $(SERVICES)


.PHONY: start
start: build ## run the application
	SOPS_AGE_KEY_FILE=$(KEY_FILE) \
	docker compose --profile dev $(COMPOSE_FILES) up $(SERVICES) $(DETACH)

.PHONY: stop
stop: ## stop the container
	 docker compose -p gaia down

.PHONY: add-admin
add-admin: ## add administrator
	uv run backend/scripts/user_management/add_local_user.py $(ADMIN_EMAIL) admin "$(ADMIN_NAME)" --admin

.PHONY: ci-local
ci-local: ## Runs CI checks locally (mirrors GitHub action workflow)
	$(MAKE) clean
	GITHUB_ACTIONS=true $(MAKE) start DETACH=--detach
	until [ "$$(docker inspect -f '{{.State.Health.Status}}' gaia-backend-dev)" = "healthy" ]; do \
		echo "  still waiting for gaia-backend ..."; \
		sleep 1; \
	done;
	./backend/src/gaia_private/prompts/run_migration.sh --purge
	python3 gaia_launcher.py test


.PHONY: clean
clean:  stop ## clean
	-$(MAKE) stop
	-docker rmi gaia-stt-SERVICES:latest
	-docker rmi gaia-backend-dev:latest
	-docker rmi gaia-frontend-dev:latest
	-docker rmi gaia-postgres:latest
	-rm secrets/age-key.txt


# Launch backend services needed for running the UI locally.
# Starts containers in detached mode and waits until they are ready to accept requests.
backend-dev-up: build
	DISABLE_AUTH=true $(MAKE) start SERVICES="backend-dev postgres stt-service" DETACH="--detach"
	until [ "$$(docker inspect -f '{{.State.Health.Status}}' gaia-backend-dev)" = "healthy" ]; do \
	  echo "  still waiting for gaia-backend ..."; \
      sleep 1; \
    done;

ui-dev-with-backend: backend-dev-up
	(cd frontend && VITE_DEV_BYPASS_AUTH=true VITE_API_BASE_URL="" npm run dev )
	-$(MAKE) stop


e2e-record: backend-dev-up
	(cd frontend && (VITE_DEV_BYPASS_AUTH=true VITE_API_BASE_URL="" npm run dev & pid=$$!; echo $$pid > tmp.pid ))
	(cd frontend && mkdir -p playwright && npx playwright codegen --output=playwright/new-test.spec.ts http://localhost:3000)
	kill $$(cat frontend/tmp.pid)
	rm frontend/tmp.pid
	-$(MAKE) stop


e2e-test: backend-dev-up
	(cd frontend && VITE_DEV_BYPASS_AUTH=true VITE_API_BASE_URL="" npx playwright test)
	-$(MAKE) stop


# =============================================================================
# Private Repository Management (Boundless Studios team only)
# =============================================================================
# Private repos are cloned as siblings and symlinked in (not subtrees)
# This keeps private content out of gaia-free's git history

.PHONY: setup-private
setup-private: ## Setup private repos (clone + symlink)
	@./setup-private.sh

.PHONY: update-private
update-private: ## Pull latest changes from gaia-private
	@cd ../gaia-private && git pull origin main

.PHONY: update-campaigns
update-campaigns: ## Pull latest changes from gaia-campaigns
	@cd ../gaia-campaigns && git pull origin main

.PHONY: check-private
check-private: ## Check if private setup is complete
	@if [ -L "backend/src/gaia_private" ] && [ -f "backend/src/gaia_private/__init__.py" ]; then \
		echo "✓ Private code is available"; \
	else \
		echo "✗ Private code not set up. Run 'make setup-private' if you have access."; \
		exit 1; \
	fi