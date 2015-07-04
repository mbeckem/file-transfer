# Important directories
APP_DIR := app
WEBAPP_DIR := webapp
ASSETS_DIR := assets
BUILD_DIR := build
DIST_DIR := dist

# Python application code.
APP_FILES := main.py run requirements.txt \
	$(shell find $(APP_DIR) -type f -name "*.py")
APP_TARGETS := $(addprefix $(DIST_DIR)/,$(APP_FILES))

# Web application code.
WEBAPP_FILES := $(shell find $(WEBAPP_DIR) -type f \( -name "*.js" -o -name "*.jsx" \))
WEBAPP_DEPENDENCY_FILE := $(WEBAPP_DIR)/dependencies.txt
WEBAPP_DEPENDENCIES := $(shell cat $(WEBAPP_DEPENDENCY_FILE))
WEBAPP_BUILD := $(BUILD_DIR)/js/main.js
WEBAPP_BUILD_DEPS := $(BUILD_DIR)/js/dependencies.js
WEBAPP_TARGETS := $(patsubst $(BUILD_DIR)/%,$(DIST_DIR)/$(ASSETS_DIR)/%,$(WEBAPP_BUILD) $(WEBAPP_BUILD_DEPS))

# Assets
ASSET_FILES := $(shell find $(ASSETS_DIR) -type f)
ASSET_TARGETS := $(addprefix $(DIST_DIR)/,$(ASSET_FILES))

# These files will just be copied over into the dist/ directory.
COPY_TARGETS := $(APP_TARGETS) $(ASSET_TARGETS)

# Build settings
DEBUG ?= 0
RELEASE := $(if $(filter 1,$(DEBUG)),0,1)

# Utilities
NPM_BIN := $(shell npm bin)
NODE_ENV := $(if $(filter 1,$(RELEASE)),production,development)
NODE_CMD = NODE_ENV=$(NODE_ENV) $(NPM_BIN)/$(1)

all: dist-app dist-webapp dist-assets

debug:
	@$(MAKE) DEBUG=1 --no-print-directory all

deps:
	@echo "Installing build-time dependencies"
	@npm install

watch: debug
	@+ DIST_DIR=$(DIST_DIR) BUILD_DIR=$(BUILD_DIR) ./watch

lint:
	@$(call NODE_CMD,eslint) --color $(WEBAPP_FILES)

clean:
	rm -rf $(DIST_DIR)/*
	rm -rf $(BUILD_DIR)/*

dist-app: $(APP_TARGETS)

dist-webapp: $(WEBAPP_TARGETS)

dist-assets: $(ASSET_TARGETS)

# Debug: Dont minify.
# Release: Depending on %.ugly.js automatically builds minified versions.
ifeq ($(RELEASE), 1)
$(WEBAPP_TARGETS): $(DIST_DIR)/$(ASSETS_DIR)/%.js: $(BUILD_DIR)/%.ugly.js
else
$(WEBAPP_TARGETS): $(DIST_DIR)/$(ASSETS_DIR)/%.js: $(BUILD_DIR)/%.js
endif
	@echo Copying $< to $@
	@mkdir -p $(@D)
	@cp -f $< $@

# Browserify will walk all required files from main.js.
$(WEBAPP_BUILD): $(WEBAPP_FILES)
	@echo "Compiling javascript file $@"
	@mkdir -p $(@D)
	@$(eval ext_deps := $(WEBAPP_DEPENDENCIES:%=-x %))
	@$(eval babel_flags := -t [babelify --loose])
ifeq ($(RELEASE), 1)
	@$(eval babel_flags += -t stripify)
endif
	@$(call NODE_CMD,browserify) $(babel_flags) $(ext_deps) $(WEBAPP_DIR)/main.js -o $@

$(WEBAPP_BUILD_DEPS): $(WEBAPP_DEPENDENCY_FILE)
	@echo "Compiling javascript dependencies $@"
	@mkdir -p $(@D)
	@$(eval ext_deps := $(WEBAPP_DEPENDENCIES:%=-r %))
	@$(call NODE_CMD,browserify) $(ext_deps) -o $@

$(BUILD_DIR)/%.ugly.js: $(BUILD_DIR)/%.js
	@echo "Minifying javascript file $@"
	@mkdir -p $(@D)
	@$(call NODE_CMD,uglifyjs) $< -c warnings=false -m -o $@

$(COPY_TARGETS): $(DIST_DIR)/%: %
	@echo Copying $< to $@
	@mkdir -p $(@D)
	@cp -f $< $@

.PHONY: all debug deps watch lint clean dist-app dist-webapp dist-assets
