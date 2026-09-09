# Dev-oriented image: source is bind-mounted over this at runtime (see
# ../docker-compose.yml) so code changes hot-reload without a rebuild.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
