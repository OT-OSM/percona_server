## Steps for Backup and Restore operations with Backup Server
Backup and restore on Percoan backup server can performed in 3 easy steps mentioned below.

### Step 1. Perform an Incremental Backup
```
sudo -u backup backup-mysql.sh
```
 It creates a full or incremental backups and automatically organizes content by day at `mysql_backup_directory`. By default, it maintains 3 days worth of backups.
```
Output
Backup successful!
Backup created at /backups/mysql/Thu/incremental-04-20-2017_17-15-03.xbstream
```
### Step 2. Extract the Backups
```
sudo -u backup extract-mysql.sh *.xbstream
```
`Note:` ***You should give the accurate path of backup files. eg: `/backups/mysql/Thu/`***

This decompresses and decrypts the backup files and create directory `restore` with the backed up content at `mysql_backup_directory`. Due to space and security considerations, this should normally only be done when you are ready to restore the data.

```
Output
Extraction complete! Backup directories have been extracted to the "restore" directory.
```
### Step 3. Prepare the Final Backup
```
sudo -u backup prepare-mysql.sh
```
`Note:` ***You should give the accurate path of backup files. eg: `/backups/mysql/Thu/restore`***

This `prepares` the back up directories by processing the files and applying logs. When you are ready to restore, make sure you are in the restore directory created with above step where your individual backup directories are located.
```
Output
Backup looks to be fully prepared.  Please check the "prepare-progress.log" file
to verify before continuing.

If everything looks correct, you can apply the restored files.

First, Copy the backup files from backup server to Percona master server:
        rsync -avprP -e ssh /backups/mysql/Thu/restore/full-04-20-2017_14-55-17 TheMaster:/path/to/backup

Then, stop MySQL at Percona master and move or remove the contents of the MySQL data directory:

        sudo systemctl stop mysql
        sudo mv /var/lib/mysql/ /tmp/

Then, recreate the data directory and copy backup files to directory

        sudo mkdir /var/lib/mysql
        sudo mv /path/to/backup /var/lib/mysql
        
        
Afterward the files are copied, adjust the permissions and restart the service at Master:
        
        sudo chown -R mysql:mysql /var/lib/mysql
        sudo find /var/lib/mysql -type d -exec chmod 750 {} \;
        sudo systemctl start mysql
```
