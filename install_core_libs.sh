#!/bin/bash
# Bash script to install core libraries
# This script installs the three core libraries: llm_adapter, moderation-service, and user_profile

# Colors for output
CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Installing Core Libraries${NC}"
echo -e "${CYAN}========================================${NC}"
echo ""

# Check if uv is available
if command -v uv &> /dev/null; then
    echo -e "${GREEN}Using 'uv' for installation${NC}"
    USE_UV=true
else
    echo -e "${YELLOW}Warning: 'uv' command not found. Falling back to pip.${NC}"
    USE_UV=false
fi

# Function to install a library
install_library() {
    local name=$1
    local path=$2
    
    echo ""
    echo -e "${CYAN}----------------------------------------${NC}"
    echo -e "${CYAN}Installing: $name${NC}"
    echo -e "${GRAY}Path: $path${NC}"
    echo -e "${CYAN}----------------------------------------${NC}"
    
    if [ ! -d "$path" ]; then
        echo -e "${RED}Error: Directory not found: $path${NC}"
        return 1
    fi
    
    if [ "$USE_UV" = true ]; then
        # Install using uv in editable mode
        echo -e "${GRAY}Running: uv pip install -e $path${NC}"
        uv pip install -e "$path"
    else
        # Install using pip in editable mode
        echo -e "${GRAY}Running: pip install -e $path${NC}"
        pip install -e "$path"
    fi
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Successfully installed $name${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to install $name${NC}"
        return 1
    fi
}

# Install each library
declare -A results

install_library "llm_adapter" "core/llm_adapter"
results[llm_adapter]=$?

install_library "moderation-service" "core/moderation-service"
results[moderation-service]=$?

install_library "user_profile" "core/user_profile"
results[user_profile]=$?

# Summary
echo ""
echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}Installation Summary${NC}"
echo -e "${CYAN}========================================${NC}"

success_count=0
fail_count=0

for lib in "${!results[@]}"; do
    if [ ${results[$lib]} -eq 0 ]; then
        echo -e "${GREEN}✓ $lib${NC}"
        ((success_count++))
    else
        echo -e "${RED}✗ $lib${NC}"
        ((fail_count++))
    fi
done

echo ""
echo -e "${CYAN}Total: ${#results[@]} libraries${NC}"
echo -e "${GREEN}Success: $success_count${NC}"
if [ $fail_count -gt 0 ]; then
    echo -e "${RED}Failed: $fail_count${NC}"
else
    echo -e "${GRAY}Failed: $fail_count${NC}"
fi
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}All libraries installed successfully! ✓${NC}"
    exit 0
else
    echo -e "${YELLOW}Some libraries failed to install. Please check the errors above.${NC}"
    exit 1
fi
