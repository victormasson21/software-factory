#!/bin/bash
set -euo pipefail

readonly USAGE="Usage: bootstrap.sh <ipv4> <owner/repo>"
readonly HOST="${1:?$USAGE}"
readonly REPO="${2:?$USAGE}"
readonly NAMESPACE="dev"
readonly TOKEN_SECRET="deployer-token"
readonly WORKFLOW="hello.yml"
readonly POLL_SECONDS=10
readonly SSH=(ssh -o StrictHostKeyChecking=accept-new "root@$HOST")

token_field() {
    "${SSH[@]}" k3s kubectl --namespace "$NAMESPACE" get secret "$TOKEN_SECRET" \
        --output "jsonpath='{.data.$1}'"
}

ssh-keygen -R "$HOST" &>/dev/null || true

echo "Waiting for k3s on $HOST" >&2
until [[ -n "$(token_field token 2>/dev/null)" ]]; do
    sleep "$POLL_SECONDS"
done

token_field token | base64 --decode | gh secret set KUBE_TOKEN --repo "$REPO"
token_field 'ca\.crt' | gh variable set KUBE_CA --repo "$REPO"
gh variable set DEV_HOST --repo "$REPO" --body "$HOST"
gh workflow run "$WORKFLOW" --repo "$REPO"
