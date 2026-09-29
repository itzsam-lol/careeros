# CareerOS web app (Next.js standalone output).
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY apps/mobile/package.json apps/mobile/
COPY packages/api-client/package.json packages/api-client/
RUN pnpm install --frozen-lockfile --filter "@careeros/web..."

FROM deps AS build
COPY apps/web apps/web
COPY packages/api-client packages/api-client
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_AUTH_MODE=password
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_AUTH_MODE=${NEXT_PUBLIC_AUTH_MODE} \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter @careeros/web build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /repo/apps/web/.next/standalone ./
COPY --from=build --chown=app:app /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=app:app /repo/apps/web/public ./apps/web/public
USER app
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
