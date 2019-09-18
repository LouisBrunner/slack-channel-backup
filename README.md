# slack-channel-backup [![Build Status](https://travis-ci.org/LouisBrunner/slack-channel-backup.svg?branch=master)](https://travis-ci.org/LouisBrunner/slack-channel-backup)

This tool allows you to backup (and potentially delete) the content of a Slack channel (including files).

## Usage

You will need to provide your own `SLACK_API_TOKEN` token as a environment variable

```
$ export SLACK_API_TOKEN=xoxp-WHATEVER
$ ./slack-backup.py '#random' --where mybackup
```

You will end up with a folder named `mybackup` containing a `conversation.txt` file with all the history and a `files` folder with the uploaded files (which are properly tagged as such in the history).

The tool also allows to control a date range for the backup and to delete the backed up history:

```
$ ./slack-backup.py -h
usage: slack-backup.py [-h] [--where WHERE] [--delete] [--from FROM] [--to TO] channel

Backup a slack channel (and potentially delete) the content of a Slack channel (including files)

positional arguments:
  channel        channel to backup (use # prefix for channels, @ prefix for DMs)

optional arguments:
  -h, --help     show this help message and exit
  --where WHERE  where to store the backup
  --delete       delete the backed up messages
  --from FROM    when to start backing/deleting up
  --to TO        when to stop backing/deleting up
```

## Required permissions

You will need to [create a Slack app](https://api.slack.com/apps) with the following permissions:

 - Always: `files:read`, `users:read`
 - When using public channels: `channels:history`, `channels:read`
 - When using private channels: `groups:history`, `groups:read`
 - When using Direct Messages: `im:history`, `im:read`
 - When deleting messages: `chat:write:user`, `files:write:user`
