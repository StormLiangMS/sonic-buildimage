#!/bin/bash

# Storm Debug Configuration Management Script
# This script helps manage the storm debug throttling configuration

CONFIG_FILE="/etc/frr/storm_debug.conf"
EXAMPLE_FILE="./storm_debug.conf.example"

show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  create      Create the configuration file with default values"
    echo "  show        Show current configuration"
    echo "  set         Set a configuration value"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 create                           # Create config with defaults"
    echo "  $0 show                            # Show current settings"
    echo "  $0 set throttle_100 50             # Set throttle_100 to 50"
    echo "  $0 set throttle_500 1000           # Set throttle_500 to 1000"
}

create_config() {
    if [ -f "$CONFIG_FILE" ]; then
        echo "Configuration file already exists at $CONFIG_FILE"
        echo "Use 'show' to see current settings or manually edit the file"
        return 1
    fi
    
    # Create directory if it doesn't exist
    mkdir -p "$(dirname "$CONFIG_FILE")"
    
    # Copy example file or create basic config
    if [ -f "$EXAMPLE_FILE" ]; then
        cp "$EXAMPLE_FILE" "$CONFIG_FILE"
    else
        tee "$CONFIG_FILE" > /dev/null << EOF
# Storm Debug Configuration File
# throttle_100: Throttle rate for frequent events (default: 100)
# throttle_500: Throttle rate for normal events (default: 500)

throttle_100=100
throttle_500=500
EOF
    fi
    
    echo "Configuration file created at $CONFIG_FILE"
    echo "FRR will automatically reload this configuration every 5 seconds"
}

show_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Configuration file not found at $CONFIG_FILE"
        echo "Use '$0 create' to create it"
        return 1
    fi
    
    echo "Current storm debug configuration:"
    echo "================================="
    grep -E "^[^#]" "$CONFIG_FILE" || echo "No active configuration found"
    echo ""
    echo "File location: $CONFIG_FILE"
    echo "Last modified: $(stat -c %y "$CONFIG_FILE" 2>/dev/null || echo "unknown")"
}

set_config() {
    local key="$1"
    local value="$2"
    
    if [ -z "$key" ] || [ -z "$value" ]; then
        echo "Error: Both key and value are required"
        echo "Usage: $0 set <key> <value>"
        return 1
    fi
    
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Configuration file not found. Creating it first..."
        create_config
    fi
    
    # Validate key
    if [[ ! "$key" =~ ^throttle_(100|500)$ ]]; then
        echo "Error: Invalid key '$key'. Valid keys are: throttle_100, throttle_500"
        return 1
    fi
    
    # Validate value (must be positive integer)
    if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
        echo "Error: Invalid value '$value'. Must be a positive integer"
        return 1
    fi
    
    # Update configuration
    if grep -q "^$key=" "$CONFIG_FILE"; then
        # Key exists, update it
        sed -i "s/^$key=.*/$key=$value/" "$CONFIG_FILE"
    else
        # Key doesn't exist, add it
        echo "$key=$value" | tee -a "$CONFIG_FILE" > /dev/null
    fi
    
    echo "Updated $key to $value"
    echo "New configuration will be applied within 5 seconds"
}

case "$1" in
    create)
        create_config
        ;;
    show)
        show_config
        ;;
    set)
        set_config "$2" "$3"
        ;;
    help|--help|-h|"")
        show_usage
        ;;
    *)
        echo "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac