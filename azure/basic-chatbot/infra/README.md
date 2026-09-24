# basic-chatbot infra

Terraform for the basic-chatbot PoC. Everything is created in one resource group, `rg-basic-chatbot`, in `swedencentral`. Auth is keyless (Entra ID and RBAC only), and nothing is hosted: the app runs locally.

| Resource | SKU | Notes |
| --- | --- | --- |
| Azure AI Search | Basic, 1 replica / 1 partition | `local_authentication_enabled = false` |
| Foundry account (`AIServices`) | S0 | `local_auth_enabled = false`, custom subdomain |
| `gpt-4.1-mini` (2025-04-14) | GlobalStandard, 30K TPM | chat |
| `text-embedding-3-small` (1) | GlobalStandard, 30K TPM | embeddings |
| Role assignments for you | - | Search Index Data Contributor, Search Service Contributor, Cognitive Services OpenAI User |

The backend creates the search index itself (default name `docs`), so Terraform does not.

## Prerequisites
- `terraform` >= 1.9 and `az` (`brew install terraform azure-cli`)
- `az login` (you do not need `az account set`, because the subscription is pinned through `subscription_id`)
- `cp terraform.tfvars.example terraform.tfvars` and fill it in. The file is gitignored.

## Commands
```bash
terraform init
terraform plan -out=tfplan
terraform apply tfplan        # only after reviewing the plan
./write-env.sh                # writes ../backend/.env (no secrets)
terraform destroy             # teardown
```
Role assignments can take a few minutes to propagate. If the backend gets a 403 right after apply, wait and try again.

## Rough cost (USD/month)
- AI Search Basic: about $75, billed hourly whether or not you use it. This is the main cost, so destroy the resources when you are done.
- Foundry S0 plus deployments: pay per token only. At PoC volume this is usually under $5.
