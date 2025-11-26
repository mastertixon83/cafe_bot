#!/bin/bash
set -e

# Переменные окружения будут переданы из docker-compose
PGHOST=$POSTGRES_HOST
PGUSER=$POSTGRES_USER
PGPASSWORD=$POSTGRES_PASSWORD
PGDATABASE=$POSTGRES_DB

# Формат имени файла бэкапа: db_backup_YYYY-MM-DD_HH-MM-SS.sql.gz
BACKUP_DIR="/backups"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
FILE_NAME="db_backup_${DATE}.sql.gz"
BACKUP_FILE="${BACKUP_DIR}/${FILE_NAME}"

# Создаем директорию для бэкапов, если она не существует
mkdir -p $BACKUP_DIR

# Команда для создания бэкапа
# pg_dump выгружает данные, а gzip сжимает их для экономии места
echo "Создание бэкапа базы данных ${PGDATABASE}..."
pg_dump -h $PGHOST -U $PGUSER -d $PGDATABASE | gzip > $BACKUP_FILE

echo "Бэкап успешно создан: ${BACKUP_FILE}"

# (Опционально) Удаление старых бэкапов (например, старше 7 дней)
find $BACKUP_DIR -type f -name "*.sql.gz" -mtime +7 -delete
echo "Старые бэкапы (старше 7 дней) удалены."