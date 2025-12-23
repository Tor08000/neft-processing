FROM alpine:3.20 AS curlstage
RUN apk add --no-cache curl

FROM otel/opentelemetry-collector-contrib:0.104.0

COPY --from=curlstage /usr/bin/curl /usr/bin/curl
COPY --from=curlstage /lib /lib
COPY --from=curlstage /usr/lib /usr/lib
