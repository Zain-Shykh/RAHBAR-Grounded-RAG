# rahbar-ui: static chat page behind nginx, non-root on 8080 (architecture 4.12).
FROM nginxinc/nginx-unprivileged:1.30.6-alpine
# Trivy: the base image lags alpine security fixes (brotli, curl, expat, zlib); pull them in.
USER root
RUN apk upgrade --no-cache
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html
USER 101
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
