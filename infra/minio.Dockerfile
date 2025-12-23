FROM alpine:3.20 AS curlstage
RUN apk add --no-cache curl

FROM quay.io/minio/minio:RELEASE.2024-09-22T00-33-43Z
COPY --from=curlstage /usr/bin/curl /usr/bin/curl
COPY --from=curlstage /lib /lib
COPY --from=curlstage /usr/lib /usr/lib
