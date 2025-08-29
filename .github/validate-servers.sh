#!/bin/bash

set -euo pipefail

if [ $# -eq 0 ]; then
    echo "Usage: $0 <path-to-Servers.xml>"
    exit 1
fi

XML_PATH="$1"
BASE_DIR=$(dirname "$XML_PATH")
XML_FILE=$(basename "$XML_PATH")
XSD_PATH="$BASE_DIR/Servers.xsd"

echo "::group::XML Validation"

if [ ! -f "$XML_PATH" ]; then
    echo "::error::$XML_PATH not found"
    exit 1
fi

if [ ! -f "$XSD_PATH" ]; then
    echo "::error::$XSD_PATH not found"
    exit 1
fi

# Run validation and capture both output and exit code
set +e  # Don't exit on command failure
xmllint --noout --schema "$XSD_PATH" "$XML_PATH" 2>&1 | tee validation_output.txt
exit_code=$?
set -e  # Re-enable exit on error

if [ $exit_code -eq 0 ]; then
    echo "XML validation Passed"
    echo "::endgroup::"
    rm -f validation_output.txt
    exit 0
else
    echo "Validation failed with exit code: $exit_code"

    # Parse output and create annotations for different types of errors
    error_found=false
    while IFS= read -r line; do
        if [[ $line == *"$XML_FILE:"* ]]; then
            # Extract line number from various error formats
            if [[ $line =~ $XML_FILE:([0-9]+): ]]; then
                line_num="${BASH_REMATCH[1]}"
                error_found=true

                # Handle different error types
                if [[ $line == *"Schemas validity error"* ]]; then
                    error_msg=$(echo "$line" | sed 's/.*Schemas validity error : //')
                    echo "::error file=$XML_PATH,line=${line_num}::Schema validation error: ${error_msg}"
                elif [[ $line == *"parser error"* ]]; then
                    error_msg=$(echo "$line" | sed 's/.*parser error : //')
                    echo "::error file=$XML_PATH,line=${line_num}::XML parser error: ${error_msg}"
                else
                    # Generic error format
                    error_msg=$(echo "$line" | sed "s/$XML_FILE:[0-9]*: //")
                    echo "::error file=$XML_PATH,line=${line_num}::${error_msg}"
                fi
            fi
        elif [[ $line == *"fails to validate"* ]]; then
            error_found=true
            echo "::error file=$XML_PATH::${line}"
        fi
    done < validation_output.txt

    if [ "$error_found" = false ]; then
        echo "::error file=$XML_PATH::XML validation failed but no specific errors could be parsed"
        cat validation_output.txt
    fi

    echo "::error file=$XML_PATH::XML validation failed - see annotations above"
    echo "::endgroup::"
    rm -f validation_output.txt
    exit 1
fi
