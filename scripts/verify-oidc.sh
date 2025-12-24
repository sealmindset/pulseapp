#!/bin/bash
# =============================================================================
# PULSE OIDC Configuration Verification Script
# =============================================================================
# This script verifies that all OIDC/SSO configuration is correctly set up
# for Microsoft Entra ID (Azure AD) authentication.
#
# Usage: ./scripts/verify-oidc.sh [--azure] [--local] [--all]
#   --azure  Check Azure App Service configuration
#   --local  Check local .env files
#   --all    Check everything (default)
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Expected values from docs/OIDC.md
EXPECTED_CLIENT_ID="9196744b-cf41-4197-9361-0eebccb3ffb6"
EXPECTED_TENANT_ID="ed8aabd5-14de-4982-9fb6-d6528851af5e"

# Azure resources
RESOURCE_GROUP="rg-PULSE-training-prod"
WEB_APP_NAME="app-PULSE-training-ui-prod"

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

print_check() {
    echo -e "${BLUE}[CHECK]${NC} $1"
}

print_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# =============================================================================
# Check Azure AD Application Registration
# =============================================================================
check_azure_ad_app() {
    print_header "Azure AD Application Registration"

    print_check "Verifying Azure AD application exists..."

    # Check if we can get application info
    APP_INFO=$(az ad app show --id "$EXPECTED_CLIENT_ID" 2>/dev/null || echo "NOT_FOUND")

    if [[ "$APP_INFO" == "NOT_FOUND" ]]; then
        print_fail "Azure AD application not found with Client ID: $EXPECTED_CLIENT_ID"
        return 1
    fi

    print_pass "Azure AD application found"

    # Extract and verify display name
    APP_NAME=$(echo "$APP_INFO" | jq -r '.displayName // "Unknown"')
    print_info "Application Name: $APP_NAME"

    # Check sign-in audience
    SIGN_IN_AUDIENCE=$(echo "$APP_INFO" | jq -r '.signInAudience // "Unknown"')
    print_info "Sign-in Audience: $SIGN_IN_AUDIENCE"

    if [[ "$SIGN_IN_AUDIENCE" == "AzureADMyOrg" ]]; then
        print_pass "Sign-in audience is correctly set to single tenant"
    else
        print_warn "Sign-in audience is '$SIGN_IN_AUDIENCE' (expected: AzureADMyOrg for single tenant)"
    fi

    # Check redirect URIs
    print_check "Verifying redirect URIs..."
    REDIRECT_URIS=$(echo "$APP_INFO" | jq -r '.web.redirectUris[]?' 2>/dev/null || echo "")

    if [[ -z "$REDIRECT_URIS" ]]; then
        print_fail "No redirect URIs configured"
    else
        print_info "Configured Redirect URIs:"
        echo "$REDIRECT_URIS" | while read -r uri; do
            echo "    - $uri"
        done

        # Check for required callback URL
        if echo "$REDIRECT_URIS" | grep -q "api/auth/callback/azure-ad"; then
            print_pass "NextAuth callback URI is configured"
        else
            print_fail "Missing NextAuth callback URI (should contain 'api/auth/callback/azure-ad')"
        fi
    fi

    # Check required API permissions
    print_check "Verifying API permissions..."
    REQUIRED_PERMISSIONS=$(echo "$APP_INFO" | jq -r '.requiredResourceAccess[]?.resourceAccess[]?.id' 2>/dev/null || echo "")

    # Microsoft Graph permissions we need:
    # openid: 37f7f235-527c-4136-accd-4a02d197296e
    # profile: 14dad69e-099b-42c9-810b-d002981feec1
    # email: 64a6cdd6-aab1-4aaf-94b8-3cc8405e90d0
    # User.Read: e1fe6dd8-ba31-4d61-89e7-88639da4683d

    if [[ -n "$REQUIRED_PERMISSIONS" ]]; then
        print_pass "API permissions are configured"
    else
        print_warn "Could not verify API permissions - check manually in Azure Portal"
    fi
}

# =============================================================================
# Check Azure App Service Configuration
# =============================================================================
check_azure_app_service() {
    print_header "Azure App Service Configuration"

    print_check "Fetching App Service settings..."

    # Get all app settings
    APP_SETTINGS=$(az webapp config appsettings list \
        --resource-group "$RESOURCE_GROUP" \
        --name "$WEB_APP_NAME" \
        2>/dev/null || echo "ERROR")

    if [[ "$APP_SETTINGS" == "ERROR" ]]; then
        print_fail "Could not fetch App Service settings. Check Azure CLI authentication."
        return 1
    fi

    # Helper to get setting value
    get_setting() {
        echo "$APP_SETTINGS" | jq -r ".[] | select(.name==\"$1\") | .value // \"NOT_SET\""
    }

    # Check AUTH_MODE
    AUTH_MODE=$(get_setting "AUTH_MODE")
    print_check "AUTH_MODE = $AUTH_MODE"
    if [[ "$AUTH_MODE" == "sso" ]]; then
        print_pass "AUTH_MODE is correctly set to 'sso'"
    else
        print_fail "AUTH_MODE should be 'sso', got '$AUTH_MODE'"
    fi

    # Check AZURE_AD_CLIENT_ID
    CLIENT_ID=$(get_setting "AZURE_AD_CLIENT_ID")
    print_check "AZURE_AD_CLIENT_ID = ${CLIENT_ID:0:8}..."
    if [[ "$CLIENT_ID" == "$EXPECTED_CLIENT_ID" ]]; then
        print_pass "AZURE_AD_CLIENT_ID matches expected value"
    else
        print_fail "AZURE_AD_CLIENT_ID mismatch (expected: $EXPECTED_CLIENT_ID)"
    fi

    # Check AZURE_AD_TENANT_ID
    TENANT_ID=$(get_setting "AZURE_AD_TENANT_ID")
    print_check "AZURE_AD_TENANT_ID = ${TENANT_ID:0:8}..."
    if [[ "$TENANT_ID" == "$EXPECTED_TENANT_ID" ]]; then
        print_pass "AZURE_AD_TENANT_ID matches expected value"
    else
        print_fail "AZURE_AD_TENANT_ID mismatch (expected: $EXPECTED_TENANT_ID)"
    fi

    # Check AZURE_AD_CLIENT_SECRET
    CLIENT_SECRET=$(get_setting "AZURE_AD_CLIENT_SECRET")
    if [[ "$CLIENT_SECRET" != "NOT_SET" && -n "$CLIENT_SECRET" ]]; then
        print_pass "AZURE_AD_CLIENT_SECRET is configured (value hidden)"
    else
        print_fail "AZURE_AD_CLIENT_SECRET is not set"
    fi

    # Check NEXTAUTH_SECRET
    NEXTAUTH_SECRET=$(get_setting "NEXTAUTH_SECRET")
    if [[ "$NEXTAUTH_SECRET" != "NOT_SET" && -n "$NEXTAUTH_SECRET" ]]; then
        # Check if it looks like a proper secret (base64, reasonable length)
        if [[ ${#NEXTAUTH_SECRET} -ge 32 ]]; then
            print_pass "NEXTAUTH_SECRET is configured (length: ${#NEXTAUTH_SECRET})"
        else
            print_warn "NEXTAUTH_SECRET seems short (length: ${#NEXTAUTH_SECRET})"
        fi
    else
        print_fail "NEXTAUTH_SECRET is not set"
    fi

    # Check NEXTAUTH_URL
    NEXTAUTH_URL=$(get_setting "NEXTAUTH_URL")
    print_check "NEXTAUTH_URL = $NEXTAUTH_URL"
    if [[ "$NEXTAUTH_URL" == *"azurewebsites.net"* || "$NEXTAUTH_URL" == *"https://"* ]]; then
        print_pass "NEXTAUTH_URL is configured"
    else
        print_fail "NEXTAUTH_URL is not properly configured"
    fi
}

# =============================================================================
# Check Local Environment Files
# =============================================================================
check_local_env() {
    print_header "Local Environment Configuration"

    UI_DIR="$(dirname "$0")/../ui"

    # Check .env.local
    if [[ -f "$UI_DIR/.env.local" ]]; then
        print_pass ".env.local file exists"

        # Source the file to get variables
        set +e
        source "$UI_DIR/.env.local" 2>/dev/null
        set -e

        # Check variables
        if [[ -n "$AZURE_AD_CLIENT_ID" ]]; then
            if [[ "$AZURE_AD_CLIENT_ID" == "$EXPECTED_CLIENT_ID" ]]; then
                print_pass "Local AZURE_AD_CLIENT_ID matches expected"
            else
                print_warn "Local AZURE_AD_CLIENT_ID differs from expected"
            fi
        else
            print_info "AZURE_AD_CLIENT_ID not in .env.local (may be using demo mode)"
        fi
    else
        print_info ".env.local not found (may be using demo mode locally)"
    fi

    # Check .env.example exists
    if [[ -f "$UI_DIR/.env.example" ]]; then
        print_pass ".env.example template exists"
    else
        print_warn ".env.example template not found"
    fi
}

# =============================================================================
# Check Terraform Configuration
# =============================================================================
check_terraform() {
    print_header "Terraform Configuration"

    TFVARS_FILE="$(dirname "$0")/../prod.tfvars"

    if [[ -f "$TFVARS_FILE" ]]; then
        print_pass "prod.tfvars file exists"

        # Check for OIDC settings
        if grep -q "auth_mode.*=.*\"sso\"" "$TFVARS_FILE"; then
            print_pass "auth_mode is set to 'sso' in tfvars"
        else
            print_fail "auth_mode is not set to 'sso' in tfvars"
        fi

        if grep -q "azure_ad_client_id" "$TFVARS_FILE"; then
            print_pass "azure_ad_client_id is configured in tfvars"
        else
            print_fail "azure_ad_client_id is not in tfvars"
        fi

        if grep -q "azure_ad_tenant_id" "$TFVARS_FILE"; then
            print_pass "azure_ad_tenant_id is configured in tfvars"
        else
            print_fail "azure_ad_tenant_id is not in tfvars"
        fi

        if grep -q "nextauth_secret" "$TFVARS_FILE"; then
            print_pass "nextauth_secret is configured in tfvars"
        else
            print_fail "nextauth_secret is not in tfvars"
        fi
    else
        print_warn "prod.tfvars not found"
    fi
}

# =============================================================================
# Test OIDC Endpoints
# =============================================================================
test_oidc_endpoints() {
    print_header "OIDC Endpoint Connectivity"

    # Test Azure AD OpenID configuration endpoint
    OPENID_CONFIG_URL="https://login.microsoftonline.com/$EXPECTED_TENANT_ID/v2.0/.well-known/openid-configuration"

    print_check "Testing Azure AD OpenID configuration endpoint..."
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$OPENID_CONFIG_URL" 2>/dev/null || echo "000")

    if [[ "$RESPONSE" == "200" ]]; then
        print_pass "Azure AD OpenID configuration endpoint is accessible"

        # Fetch and display key information
        CONFIG=$(curl -s "$OPENID_CONFIG_URL" 2>/dev/null)
        ISSUER=$(echo "$CONFIG" | jq -r '.issuer // "Unknown"')
        AUTH_ENDPOINT=$(echo "$CONFIG" | jq -r '.authorization_endpoint // "Unknown"')
        TOKEN_ENDPOINT=$(echo "$CONFIG" | jq -r '.token_endpoint // "Unknown"')

        print_info "Issuer: $ISSUER"
        print_info "Auth Endpoint: ${AUTH_ENDPOINT:0:60}..."
        print_info "Token Endpoint: ${TOKEN_ENDPOINT:0:60}..."
    else
        print_fail "Could not reach Azure AD OpenID configuration (HTTP $RESPONSE)"
    fi

    # Test the application endpoint
    APP_URL="https://$WEB_APP_NAME.azurewebsites.net"

    print_check "Testing application endpoint..."
    APP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL" 2>/dev/null || echo "000")

    if [[ "$APP_RESPONSE" == "200" || "$APP_RESPONSE" == "302" ]]; then
        print_pass "Application endpoint is accessible (HTTP $APP_RESPONSE)"
    elif [[ "$APP_RESPONSE" == "503" ]]; then
        print_fail "Application is returning 503 (Service Unavailable)"
    else
        print_warn "Application returned HTTP $APP_RESPONSE"
    fi

    # Test NextAuth callback route
    CALLBACK_URL="$APP_URL/api/auth/providers"
    print_check "Testing NextAuth providers endpoint..."
    PROVIDERS_RESPONSE=$(curl -s "$CALLBACK_URL" 2>/dev/null || echo "{}")

    if echo "$PROVIDERS_RESPONSE" | jq -e '.["azure-ad"]' > /dev/null 2>&1; then
        print_pass "Azure AD provider is configured in NextAuth"
    elif [[ "$APP_RESPONSE" == "503" ]]; then
        print_warn "Cannot test NextAuth - application is not running"
    else
        print_warn "Could not verify Azure AD provider in NextAuth"
    fi
}

# =============================================================================
# Main Execution
# =============================================================================
main() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       PULSE OIDC Configuration Verification Script           ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Timestamp: $(date)"
    echo "Expected Client ID: $EXPECTED_CLIENT_ID"
    echo "Expected Tenant ID: $EXPECTED_TENANT_ID"

    CHECK_AZURE=false
    CHECK_LOCAL=false
    CHECK_ALL=true

    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --azure)
                CHECK_AZURE=true
                CHECK_ALL=false
                ;;
            --local)
                CHECK_LOCAL=true
                CHECK_ALL=false
                ;;
            --all)
                CHECK_ALL=true
                ;;
            --help|-h)
                echo "Usage: $0 [--azure] [--local] [--all]"
                echo "  --azure  Check Azure App Service configuration"
                echo "  --local  Check local .env files"
                echo "  --all    Check everything (default)"
                exit 0
                ;;
        esac
    done

    # Run checks
    if [[ "$CHECK_ALL" == true ]]; then
        check_azure_ad_app
        check_azure_app_service
        check_local_env
        check_terraform
        test_oidc_endpoints
    else
        [[ "$CHECK_AZURE" == true ]] && check_azure_app_service
        [[ "$CHECK_LOCAL" == true ]] && check_local_env
    fi

    # Summary
    print_header "Verification Summary"
    echo ""
    echo -e "  ${GREEN}Passed:${NC}   $PASSED"
    echo -e "  ${RED}Failed:${NC}   $FAILED"
    echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
    echo ""

    if [[ $FAILED -gt 0 ]]; then
        echo -e "${RED}Some checks failed. Please review the issues above.${NC}"
        exit 1
    elif [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}All critical checks passed, but there are warnings to review.${NC}"
        exit 0
    else
        echo -e "${GREEN}All checks passed! OIDC configuration looks good.${NC}"
        exit 0
    fi
}

main "$@"
