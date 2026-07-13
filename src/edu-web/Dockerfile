# ---- Build stage ----
FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_SERVER_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_AVATAR_SERVER_URL
ARG VITE_AVATAR_APP_ID
ARG VITE_AVATAR_API_KEY
ARG VITE_AVATAR_API_SECRET
ARG VITE_AVATAR_SCENE_ID
ARG VITE_AVATAR_ID
ARG VITE_AVATAR_VCN

ENV VITE_SERVER_URL=$VITE_SERVER_URL \
    VITE_SUPABASE_URL=$VITE_SUPABASE_URL \
    VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY \
    VITE_AVATAR_SERVER_URL=$VITE_AVATAR_SERVER_URL \
    VITE_AVATAR_APP_ID=$VITE_AVATAR_APP_ID \
    VITE_AVATAR_API_KEY=$VITE_AVATAR_API_KEY \
    VITE_AVATAR_API_SECRET=$VITE_AVATAR_API_SECRET \
    VITE_AVATAR_SCENE_ID=$VITE_AVATAR_SCENE_ID \
    VITE_AVATAR_ID=$VITE_AVATAR_ID \
    VITE_AVATAR_VCN=$VITE_AVATAR_VCN

# Copy manifest files first for better caching
COPY package.json package-lock.json ./

# Copy source code and install deps
COPY . .
RUN npm ci

# Build the Vite SPA (static output in /dist)
RUN npm run build

# ---- Runtime stage ----
FROM nginx:alpine

# Copy SPA-friendly nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
