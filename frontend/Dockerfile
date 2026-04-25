FROM node:22-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json .npmrc ./
RUN npm ci

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Run dev server with hot-reload
CMD ["npm", "run", "dev"]
