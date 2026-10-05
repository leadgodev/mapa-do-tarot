FROM node:22-alpine
WORKDIR /app
COPY index.html termos.html privacidade.html obrigado.html ./
COPY pt ./pt
COPY es ./es
COPY assets ./assets
COPY painel ./painel
COPY upsell-cigano ./upsell-cigano
COPY js ./js
COPY server ./server
ENV PORT=80 DATA_DIR=/data
EXPOSE 80
CMD ["node", "server/index.mjs"]
