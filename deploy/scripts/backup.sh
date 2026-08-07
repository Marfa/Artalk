#!/bin/bash
set -euo pipefail
BACKUP_ROOT=/opt/artalk/backups
DATA=/opt/artalk/data
STAMP=$(date -u +%Y%m%d-%H%M%S)
DEST="$BACKUP_ROOT/$STAMP"
mkdir -p "$DEST"

docker exec artalk sh -c 'command -v sqlite3 >/dev/null || apk add --no-cache sqlite >/dev/null; sqlite3 /data/artalk.db ".backup /data/_backup_tmp.db"'
mv "$DATA/_backup_tmp.db" "$DEST/artalk.db"

docker exec artalk artalk export /data/_export_tmp.artrans
mv "$DATA/_export_tmp.artrans" "$DEST/comments.artrans"

cp -a "$DATA/artalk.yml" "$DEST/artalk.yml" 2>/dev/null || true
if [ -d "$DATA/artalk-img" ]; then
  tar -C "$DATA" -czf "$DEST/artalk-img.tar.gz" artalk-img
fi

tar -C "$BACKUP_ROOT" -czf "$BACKUP_ROOT/artalk-$STAMP.tar.gz" "$STAMP"
rm -rf "$DEST"

find "$BACKUP_ROOT" -type f -name 'artalk-*.tar.gz' -mtime +7 -delete
ls -1t "$BACKUP_ROOT"/artalk-*.tar.gz 2>/dev/null | tail -n +9 | xargs -r rm -f

echo "OK $BACKUP_ROOT/artalk-$STAMP.tar.gz ($(du -h "$BACKUP_ROOT/artalk-$STAMP.tar.gz" | cut -f1))"
