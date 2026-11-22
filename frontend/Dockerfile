FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# As rewrites (/api -> backend) são fixadas no build, por isso API_URL entra como build arg
ARG API_URL=http://api:8000
ENV API_URL=${API_URL} \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
