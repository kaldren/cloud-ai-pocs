# basic-chatbot infra

Terraform for the basic-chatbot PoC. Everything is created in one resource group, `rg-basic-chatbot`, in `swedencentral`. Auth is keyless (Entra ID and RBAC only). The frontend and backend run as containers in Azure Container Apps, and you can still run them locally against the same Azure resources.

| Resource | SKU | Notes |
| --- | --- | --- |
| Azure AI Search | Basic, 1 replica / 1 partition | `local_authentication_enabled = false` |
| Foundry account (`AIServices`) | S0 | `local_auth_enabled = false`, custom subdomain |
| `gpt-4.1-mini` (2025-04-14) | GlobalStandard, 30K TPM | chat |
| `text-embedding-3-small` (1) | GlobalStandard, 30K TPM | embeddings |
| Container registry (`acr...`) | Basic | `admin_enabled = false`; images are built with `az acr build` |
| Log Analytics workspace (`log-basic-chatbot`) | PerGB2018, 30-day retention | logs for the Container Apps environment |
| Container Apps environment (`cae-basic-chatbot`) | Consumption only | no workload profiles |
| Managed identity (`id-basic-chatbot`) | - | shared by both apps: AcrPull, Cognitive Services OpenAI User, Search Index Data Contributor, Search Service Contributor |
| `ca-basic-chatbot-api` (backend) | 0.25 vCPU / 0.5 GiB, 0-1 replicas | **internal** ingress on port 8000; uses `AZURE_CLIENT_ID` to select the managed identity |
| `ca-basic-chatbot-web` (frontend) | 0.25 vCPU / 0.5 GiB, 0-1 replicas | external ingress on port 8080; `BACKEND_URL` = the backend's internal FQDN |
| Role assignments for you | - | Search Index Data Contributor, Search Service Contributor, Cognitive Services OpenAI User, AcrPush |

The backend creates the search index itself (default name `docs`), so Terraform does not.

Terraform creates both container apps with a public placeholder image (`mcr.microsoft.com/k8se/quickstart`) and ignores image changes after that. `deploy.sh` owns the image tags, so `terraform apply` never rolls an app back.

## Prerequisites
- `terraform` >= 1.9 and `az` (`brew install terraform azure-cli`)
- `az login` (you do not need `az account set`, because the subscription is pinned through `subscription_id`, and `deploy.sh` passes it to `az` too)
- `cp terraform.tfvars.example terraform.tfvars` and fill it in. The file is gitignored.

## Commands
```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan        # only after reviewing the plan
./write-env.sh                # writes ../backend/.env (no secrets) for local runs
./deploy.sh                   # az acr build both images, update both container apps, print the URL
terraform destroy             # teardown
```
Run `./deploy.sh` again after every code change. It tags images with the short git SHA, or with a timestamp outside git.

Role assignments can take a few minutes to propagate. If the backend gets a 403, or an app can't pull its image right after apply, wait and run `./deploy.sh` again. The apps scale to zero, so the first request after an idle period has a cold start of a few seconds.

## Rough cost (USD/month)
- AI Search Basic: about $75, billed hourly whether or not you use it. This is the main cost, so destroy the resources when you are done.
- Foundry S0 plus deployments: pay per token only. At PoC volume this is usually under $5.
- Container registry Basic: about $5. ACR Tasks build time (`az acr build`) is billed per second and costs cents per build.
- Container Apps (Consumption, scale to zero): replicas bill only while they run. At PoC volume this stays within the monthly free grant (180,000 vCPU-s, 360,000 GiB-s, 2M requests), so about $0.
- Log Analytics: pay per GB ingested. The first 5 GB/month are free, and a scale-to-zero PoC stays well under that.
