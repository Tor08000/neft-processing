FROM nginx:1.27-alpine

# Copy gateway configuration
COPY services/gateway/nginx.conf /etc/nginx/conf.d/default.conf

# Ensure log output is sent to stdout/stderr
# NOTE: nginx -t не выполняется на этапе build,
# т.к. upstream-хосты не существуют до запуска docker-compose.
# Проверка конфига выполняется при реальном старте контейнера.
RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

CMD ["nginx", "-g", "daemon off;"]
