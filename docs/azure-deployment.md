# Planned Azure deployment

This is a standalone prototype, not a COLA integration or a government-authorized production system. An Azure subscription and a signed-in Azure CLI are needed. These instructions create billable resources; choose a region and budget before running them.

## Container route

Use Azure Container Apps with Azure Container Registry. The image includes Tesseract, so user browsers contact only the app URL and inference happens inside the same container. Container image builds need package registries; running inference needs no external AI API. Network reachability to the app domain still requires the organization's approval.

The following is a deployment template, not an executed deployment. Replace the resource names with unique values. Container Registry names must be globally unique, lowercase letters and digits.

```bash
az login
az group create --name label-check-rg --location eastus
az acr create --resource-group label-check-rg --name YOURUNIQUEREGISTRY --sku Basic
az acr build --registry YOURUNIQUEREGISTRY --image label-check:v1 .
az containerapp env create --name label-check-env --resource-group label-check-rg --location eastus
az identity create --name label-check-pull --resource-group label-check-rg
LABEL_PULL_ID=$(az identity show --name label-check-pull --resource-group label-check-rg --query id -o tsv)
LABEL_PULL_PRINCIPAL=$(az identity show --name label-check-pull --resource-group label-check-rg --query principalId -o tsv)
LABEL_REGISTRY_ID=$(az acr show --name YOURUNIQUEREGISTRY --query id -o tsv)
az role assignment create --assignee-object-id "$LABEL_PULL_PRINCIPAL" \
  --assignee-principal-type ServicePrincipal --role AcrPull --scope "$LABEL_REGISTRY_ID"
# Allow the role assignment to propagate before creating the app.
az containerapp create --name label-check --resource-group label-check-rg \
  --environment label-check-env \
  --image YOURUNIQUEREGISTRY.azurecr.io/label-check:v1 \
  --registry-server YOURUNIQUEREGISTRY.azurecr.io \
  --registry-identity "$LABEL_PULL_ID" --user-assigned "$LABEL_PULL_ID" \
  --target-port 8000 --ingress external \
  --cpu 1.0 --memory 2Gi --min-replicas 1 --max-replicas 2
```

The commands grant the user-assigned managed identity `AcrPull` on the registry before the private image is pulled. Your Azure account needs permission to create role assignments. The registry must allow ARM audience tokens; verify with `az acr config authentication-as-arm show -r YOURUNIQUEREGISTRY`. Validate the exact CLI flags against the installed Azure CLI before deployment. See [Microsoft's managed identity image-pull guide](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull).

Keep at least one replica running to avoid scale-to-zero startup delay. This incurs ongoing charges and does not guarantee a five-second response. Set Azure budget alerts and validate concurrency, resource usage, and image-to-result timing before publishing performance claims.

## Verification before handing over a URL

- Build and test the Docker image with its Linux Tesseract provider.
- Check `/api/health`, upload each fixture, compare per-check expected outcomes.
- Test representative front/back photos, unreadable images, and unavailable OCR.
- Measure upload-to-result p50/p95 and cold starts in Azure, plus multi-image requests and simultaneous reviewers.
- Check mobile upload, keyboard navigation, and readable focus/status feedback.
- Configure HTTPS ingress, request-size limits, appropriate access controls, and resource budget alerts.

At this milestone, no Azure resource has been created and no publicly deployed application URL exists.
