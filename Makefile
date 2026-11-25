CC ?= gcc
CFLAGS ?= -Wall -Wextra -Wpedantic -O2
BUILD_DIR := build
TARGET := $(BUILD_DIR)/process_control
SOURCE := c_engine/process_control.c

.PHONY: all clean test
all: $(TARGET)

$(TARGET): $(SOURCE)
	mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $(SOURCE) -o $(TARGET)

clean:
	rm -rf $(BUILD_DIR)

test: all
	python3 -m pytest -q
