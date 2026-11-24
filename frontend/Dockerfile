FROM node:20-alpine

WORKDIR /app

# Les variables NEXT_PUBLIC_* sont gravées à la compilation.
ARG NEXT_PUBLIC_API_URL=""
ARG NEXT_PUBLIC_COMPANY_ID="EXPLEO-IT-001"
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_COMPANY_ID=$NEXT_PUBLIC_COMPANY_ID \
    NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
