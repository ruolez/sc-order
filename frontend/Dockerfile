FROM nginx:alpine

# Copy static files
COPY static /usr/share/nginx/html/static
COPY templates/index.html /usr/share/nginx/html/index.html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
