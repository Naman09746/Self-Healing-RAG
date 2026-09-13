# AcmeCloud — Data Retention, Lifecycle & Backup Management

## 1. Account Deletion Policy
* **Grace Period**: When an administrator deletes an Enterprise or Professional account, primary data enters a soft-deleted state and is **retained for 30 days** before permanent removal from production databases. During this 30-day window, account restoration can be requested through customer support.
* **Permanent Destruction**: After the 30-day grace period expires, all active production tables, search indexes, and vector embeddings are permanently wiped.

## 2. Backup Retention & Persistence
* **Daily Snapshots**: Automated differential and full database snapshots are executed daily across redundant regional availability zones.
* **Backup Persistence**: Disaster recovery snapshots and immutable system backups **may persist for up to 90 days** following account deletion, after which backup cycles naturally overwrite and purge all historical archives.
