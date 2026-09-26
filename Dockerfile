FROM node:22-alpine
WORKDIR /app
COPY index.html termos.html privacidade.html ./
COPY pt ./pt
COPY assets ./assets
COPY painel ./painel
COPY server ./server
ENV PORT=80 DATA_DIR=/data
EXPOSE 80
CMD ["node", "server/index.mjs"]
