#!/bin/bash

##################################################################################################
##################################################################################################
# Created by Sam Insanali
# GitHub: https://github.com/SInsanali
##################################################################################################
##################################################################################################
# Description:
# This script reads host aliases from ~/.ssh/config and lets the user SSH into a selected host.
##################################################################################################
##################################################################################################

# Define colors
GREEN="\e[32m"
RED="\e[31m"
RESET="\e[0m"

# Verify ~/.ssh/config exists
CONFIG_FILE="$HOME/.ssh/config"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}[ ! ]${RESET} SSH config file not found at $CONFIG_FILE"
    exit 1
fi

# Extract host aliases (excluding wildcards like *)
mapfile -t HOSTS < <(grep -E "^Host\s+" "$CONFIG_FILE" | awk '{print $2}' | grep -v '\*')

# Check if any hosts were found
if [ ${#HOSTS[@]} -eq 0 ]; then
    echo -e "${RED}[ ! ]${RESET} No host entries found in $CONFIG_FILE"
    exit 1
fi

# Display host list
echo -e "\n${GREEN}[ + ]${RESET} Select a host to SSH into:"
printf "\n%-5s %-30s\n" "Num" "Host Alias"
echo "----------------------------------------"
for i in "${!HOSTS[@]}"; do
    num=$((i+1))
    printf "%-5s %-30s\n" "$num" "${HOSTS[$i]}"
done

# Prompt user for selection
read -p $'\n[ ? ] Enter the number of the host you want to SSH to: ' choice

# Validate input
if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#HOSTS[@]}" ]; then
    echo -e "\n${RED}[ ! ]${RESET} Invalid selection. Exiting."
    exit 1
fi

# SSH into selected host
HOST_ALIAS="${HOSTS[$((choice-1))]}"
echo -e "\n${GREEN}[ + ]${RESET} Connecting to $HOST_ALIAS ..."
ssh "$HOST_ALIAS"
