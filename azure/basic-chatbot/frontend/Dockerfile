FROM node:24-alpine AS build
# pnpm comes from Corepack, pinned by "packageManager" in package.json.
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Serves the static build and proxies /api/* to the backend's internal ingress
# (BACKEND_URL is set by Terraform), so the browser only ever talks to this app.
FROM nginxinc/nginx-unprivileged:1.30-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
