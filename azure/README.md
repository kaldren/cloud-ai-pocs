# Azure PoCs

## Setup
```bash
az login
az account set --subscription <subscription-id>
```
- Default region: `<region>`
- Use a dedicated resource group per PoC (`rg-<poc-name>`) so teardown is a single `az group delete`.

## PoCs
| PoC | Status | Summary |
| --- | ------ | ------- |
