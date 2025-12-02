FROM nginx:1.27-alpine

# Copy gateway configuration
COPY services/gateway/nginx.conf /etc/nginx/conf.d/default.conf

# Ensure log output is sent to stdout/stderr
RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

CMD ["nginx", "-g", "daemon off;"]
