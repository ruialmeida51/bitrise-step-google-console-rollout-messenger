#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "🚀 Checking phased release information for: ${package_name}"

echo "Using local content credentials"
echo "$service_account_json_key_content" > "${SCRIPT_DIR}/credentials.json"

cat ${SCRIPT_DIR}/credentials.json

CREDENTIALS_FILE="${SCRIPT_DIR}/credentials.json"

echo "Creating menv"
python3 -m venv env
source env/bin/activate

echo "Installing pip requirements"
pip install urllib3 pyparsing==3.1.4 google-api-python-client==2.86.0 oauth2client

echo "Running: "${SCRIPT_DIR}/phased_release_messenger.py" "${track}" "${rollout_increase_steps}" "${package_name}" "${teams_webhook_url}" "$CREDENTIALS_FILE""
python "${SCRIPT_DIR}/phased_release_messenger.py" "${track}" "${rollout_increase_steps}" "${package_name}" "${teams_webhook_url}" "$CREDENTIALS_FILE"

echo "🧹 Cleaning up build..."

deactivate
rm $CREDENTIALS_FILE

echo "✅ Script ran successfully."