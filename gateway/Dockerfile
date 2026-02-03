FROM nginx:1.27-alpine

RUN apk add --no-cache curl

# Copy gateway configuration
COPY gateway/default.conf /etc/nginx/conf.d/default.conf

# Ensure log output is sent to stdout/stderr and prepare dedicated OTEL-friendly paths
RUN mkdir -p /var/log/nginx/otel \
    && ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stdout /var/log/nginx/otel/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && ln -sf /dev/stderr /var/log/nginx/gateway.error.log

CMD ["nginx", "-g", "daemon off;"]
