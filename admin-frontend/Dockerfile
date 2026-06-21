FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 4300

# --poll enables file-watching for changes made through Docker bind mounts
CMD ["npm", "start", "--", "--host", "0.0.0.0", "--poll", "2000"]
