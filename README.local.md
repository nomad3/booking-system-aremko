# Local Development Environment Setup

This guide explains how to set up and run the Aremko Booking System in a local development environment using Docker Compose.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Setup Instructions

1. Clone the repository (if you haven't already):
   ```bash
   git clone <repository-url>
   cd booking-system-aremko
   ```

2. The `.env` file has been created with default development settings. You can modify it if needed.

3. Build and start the Docker containers:
   ```bash
   docker-compose up --build
   ```

4. Wait for the services to start up. You should see output indicating that the Django development server is running.

## Accessing the Services

- **Django Application**: http://localhost:8000
  - Admin login: `admin` / `adminpassword` (as configured in .env)

- **PostgreSQL Database**:
  - Host: `localhost`
  - Port: `5432`
  - Database: `aremko_db`
  - Username: `aremko_user`
  - Password: `aremko_password`

- **pgAdmin (Database Management)**:
  - URL: http://localhost:5050
  - Login: `admin@example.com` / `admin`
  - To connect to the database, create a new server in pgAdmin with:
    - Name: `Local Aremko DB`
    - Host: `db` (use this hostname, not localhost, as pgAdmin runs inside Docker)
    - Port: `5432`
    - Database: `aremko_db`
    - Username: `aremko_user`
    - Password: `aremko_password`

## Common Commands

- Start the services:
  ```bash
  docker-compose up
  ```

- Start the services in detached mode (background):
  ```bash
  docker-compose up -d
  ```

- Stop the services:
  ```bash
  docker-compose down
  ```

- View logs:
  ```bash
  docker-compose logs
  ```

- View logs for a specific service:
  ```bash
  docker-compose logs web
  ```

- Run Django management commands:
  ```bash
  docker-compose exec web python manage.py <command>
  ```

- Create a Django superuser (if needed):
  ```bash
  docker-compose exec web python manage.py createsuperuser
  ```

- Access the database shell:
  ```bash
  docker-compose exec db psql -U aremko_user -d aremko_db
  ```

## Development Workflow

1. The code is mounted as a volume, so any changes you make to the code will be reflected immediately.
2. The Django development server will automatically reload when you make changes to the code.
3. If you add new dependencies to `requirements.txt`, you'll need to rebuild the containers:
   ```bash
   docker-compose down
   docker-compose up --build
   ```

## Troubleshooting

- **Database connection issues**: Make sure the database container is running and healthy:
  ```bash
  docker-compose ps
  ```

- **Permission issues with volumes**: If you encounter permission issues with the volumes, you may need to adjust the permissions:
  ```bash
  sudo chown -R $USER:$USER .
  ```

- **Port conflicts**: If you have services already running on ports 8000, 5432, or 5050, you can modify the port mappings in the `docker-compose.yml` file.

- **Container won't start**: Check the logs for errors:
  ```bash
  docker-compose logs
  ```

## Data Persistence

- Database data is stored in a Docker volume named `postgres_data`
- Static files are stored in a Docker volume named `static_volume`
- Media files are stored in a Docker volume named `media_volume`

To remove these volumes and start fresh:
```bash
docker-compose down -v
```
hola