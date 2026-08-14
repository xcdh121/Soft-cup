# ---- Build stage ----
FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_SERVER_URL
ARG VITE_AVATAR_SERVER_URL
ARG VITE_AVATAR_APP_ID
ARG VITE_AVATAR_API_KEY
ARG VITE_AVATAR_API_SECRET
ARG VITE_AVATAR_SCENE_ID
ARG VITE_AVATAR_ID
ARG VITE_AVATAR_VCN

ENV VITE_SERVER_URL=$VITE_SERVER_URL \
    VITE_AVATAR_SERVER_URL=$VITE_AVATAR_SERVER_URL \
    VITE_AVATAR_APP_ID=$VITE_AVATAR_APP_ID \
    VITE_AVATAR_API_KEY=$VITE_AVATAR_API_KEY \
    VITE_AVATAR_API_SECRET=$VITE_AVATAR_API_SECRET \
    VITE_AVATAR_SCENE_ID=$VITE_AVATAR_SCENE_ID \
    VITE_AVATAR_ID=$VITE_AVATAR_ID \
    VITE_AVATAR_VCN=$VITE_AVATAR_VCN

# The production build uses the repository root as its Docker context because
# the current UI imports shared image assets from src/source.
# Copy manifest files first for better caching.
COPY src/edu-web/package.json src/edu-web/package-lock.json ./

# Copy source code and install deps
COPY src/edu-web .
COPY src/source /source
# Payment QR images are private deployment assets kept outside the public
# source directory. Copy them into Vite's public tree only inside the build.
COPY payment-codes /app/public/payment-codes
RUN npm ci

# Build the Vite SPA (static output in /dist)
RUN npm run build

# ---- Runtime stage ----
FROM nginx:alpine

# Copy SPA-friendly nginx config
COPY src/edu-web/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
