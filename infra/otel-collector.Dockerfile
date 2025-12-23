FROM otel/opentelemetry-collector-contrib:0.104.0

USER root
RUN apk add --no-cache curl

USER 10001
