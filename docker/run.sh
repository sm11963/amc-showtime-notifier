#!/bin/sh

set -e

# Ensure we have shadow (necessary in alpine for user/group mod)
apk add --quiet --no-cache shadow > /dev/null
apk add --quiet --no-cache su-exec > /dev/null

# Process user and group ids/names
PUID=${PUID:-9001}
PGID=${PGID:-9001}
PUSER="docker_internal"
PGROUP="docker_internal"

if [ "$PUID" -eq "0" ] || [ "$PGID" -eq "0" ] ; then
  >&2 echo "ERROR!!!"
  >&2 echo "Specified PUID or PGID appears to be root!"
  >&2 echo "  PUID: $PUID, PGID: $PGID"
  >&2 echo "Aborting."
  >&2 echo "Please set user and group to a safe value."
  exit 1
fi

# Create $PGROUP if it doesn't exist
if ! getent group "$PGROUP" > /dev/null 2>&1; then
  >&2 echo "Group '$PGROUP' does not exist yet, creating group."
  addgroup \
    --gid "$PGID" \
    "$PGROUP" > /dev/null
fi

# Create $PUSER if it doesn't exist
if ! id -u "$PUSER" > /dev/null 2>&1; then
  >&2 echo "User '$PUSER' does not exist yet, creating user."
  adduser \
    --disabled-password \
    --gecos "" \
    --no-create-home \
    --uid "$PUID" \
    --ingroup "$PGROUP" \
    "$PUSER" > /dev/null
fi

CURR_UID="$(id -u "$PUSER")"
CURR_GID="$(id -g "$PUSER")"

if [ "$CURR_UID" -ne "$PUID" ]; then
  echo "Modifying ownership of files belonging to user ${PUSER}."
  find / -user "$CURR_UID" -exec chown "$PUID":"$PGID" {} \; 2>/dev/null
fi

if [ "$CURR_GID" -ne "$PGID" ]; then
  echo "Modifying ownership of files belonging to group ${PGROUP}."
  find / -group "$CURR_GID" -exec chown "$PUID":"$PGID" {} \; 2>/dev/null
fi

# Update user and group to have the specified UID & GID
groupmod --gid "$PGID" --non-unique "$PGROUP" > /dev/null
usermod --uid "$PUID" --gid "$PGID" --non-unique "$PUSER" > /dev/null

# Run configuration scripts as root still with access to the user/group
export PUSER
export PGROUP
/var/local/bin/configure-app.sh
/var/local/bin/configure-cron.sh

# Get existing number of lines in the log
CRON_LINES=$(wc -l < /data/cron.log)

# Note that we execute crond as root since this is required, but executions of the
# application will be at the specified priviledge
crond -L /data/cron.log

# Use reduced priviledges for the ongoing process
exec su-exec "$PUSER":"$PGROUP" tail -n "+$((CRON_LINES + 1))" -f /data/cron.log
