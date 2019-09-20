#!/usr/bin/env python3

import os
import argparse
import sys
import time
from datetime import datetime


import slack
import requests
from tqdm import tqdm


def read_all_messages(client, func_name, channel, oldest=None, latest=None):
    func = getattr(client, func_name)
    args = {'channel': channel, 'count': 1000}
    if oldest is not None:
        args['oldest'] = oldest
    if latest is not None:
        args['latest'] = latest

    messages = []
    r = func(**args)
    messages = r['messages']
    while r['has_more']:
        if latest is not None:
            args['latest'] = messages[-1]['ts']
        else:
            args['oldest'] = messages[0]['ts']
        r = func(**args)
        if oldest is not None and latest is None:
            messages[:0] = r['messages']
        else:
            messages.extend(r['messages'])
    return messages


def read_all(client, kind, func_name, get_display, find=None):
    func = getattr(client, func_name)

    r = func(limit=200)
    raw_list = r[kind]
    while r['response_metadata']['next_cursor'] != '':
        r = func(limit=200, cursor=r['response_metadata']['next_cursor'])
        raw_list.extend(r[kind])

    list = {}
    found = None
    for raw in raw_list:
        display_name = get_display(raw)
        list[raw['id']] = display_name
        if find == display_name:
            found = raw['id']
    return list, found


def read_all_users(client, find_user=None):
    return read_all(client, 'members', 'users_list', lambda u: u['profile']['display_name'], find_user)


def read_all_channels(client, find_channel=None):
    return read_all(client, 'channels', 'channels_list', lambda c: c['name'], find_channel)


def parse_message(message, files_path, token):
    what = message['text']
    if what == '':
        parts = []
        if 'files' in message:
            os.makedirs(files_path, exist_ok=True)

            files = []
            for file in message['files']:
                name = f'{file["id"]}.{file["filetype"]}'
                with open(os.path.join(files_path, name), 'wb') as f:
                    r = requests.get(file['url_private'], headers={'Authorization': f'Bearer {token}'})
                    f.write(r.content)
                what_i = f'{{media}} <files/{name}>'
                files.append(what_i)
            parts.append(' & '.join(files))

        if 'attachments' in message:
            attachments = []
            for attachment in message['attachments']:
                what_i = f'{{attach}} {attachment["fallback"]}'
                attachments.append(what_i)
            parts.append(' & '.join(attachments))

        what = ' + '.join(parts)

    if 'thread_ts' in message:
        what = '{thread} ' + what

    return what


def assert_arg(find, found, label):
    if find is not None and found is None:
        print(f'error: could not find {label} {find}')
        sys.exit(1)


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def prompt(message):
    try:
        result = input('{} [y/N] '.format(message))
        return result.lower() == 'y'
    except (EOFError, KeyboardInterrupt):
        return False


def main():
    token = os.environ['SLACK_API_TOKEN']
    default_folder = f'slack-backup-{datetime.now().strftime("%Y-%m-%dT%H-%M-%S")}'

    parser = argparse.ArgumentParser(description='Backup a slack channel (and potentially delete) the content of a Slack channel (including files)')
    parser.add_argument('channel', help='channel to backup (use # prefix for channels, @ prefix for DMs)')
    parser.add_argument('--where', default=default_folder, help='where to store the backup')
    parser.add_argument('--delete', action='store_true', help='delete the backed up messages')
    parser.add_argument('--from', dest='frm', type=valid_date, help='when to start backing/deleting up')
    parser.add_argument('--to', type=valid_date, help='when to stop backing/deleting up')
    args = parser.parse_args()

    root = args.where

    client = slack.WebClient(token=token)

    print('Retrieving users...')
    find_user = None
    find_channel = None
    prefix = args.channel[0]
    if prefix == '@':
        find_user = args.channel[1:]
    elif prefix == '#':
        find_channel = args.channel[1:]
    users, found_user = read_all_users(client, find_user)
    found_channel = None
    if find_channel is not None:
        _, found_channel = read_all_channels(client, find_channel)

    assert_arg(find_user, found_user, 'user')
    assert_arg(find_channel, found_channel, 'channel')

    read_args = {}
    if args.frm is not None:
        read_args['oldest'] = str(args.frm.timestamp())
    if args.to is not None:
        read_args['latest'] = str(args.to.timestamp())

    print('Retrieving messages...')
    os.makedirs(root, exist_ok=True)
    files_path = os.path.join(root, 'files')
    messages = []
    channel = None
    if found_user is not None:
        conv = client.conversations_open(users=[found_user])
        channel = conv['channel']['id']
        messages = read_all_messages(client, 'im_history', channel, **read_args)
    else:
        channel = found_channel
        messages = read_all_messages(client, 'channel_history', channel, **read_args)

    print('Processing messages...')
    with open(os.path.join(root, 'conversation.txt'), 'w') as f:
        for message in tqdm(reversed(messages), total=len(messages)):
            when = datetime.utcfromtimestamp(float(message['ts'])).strftime('%Y-%m-%d %H:%M:%S')
            who = users.get(message['user'], '!Unknown!')
            what = parse_message(message, files_path, token)
            f.write(f'[{when}] {who}: {what}\n')

    if args.delete:
        if not prompt('Are you sure you want to delete all these messages? (CANNOT BE UNDONE!)'):
            sys.exit(1)
        print('Deleting messages...')
        user = client.auth_test()['user_id']
        for message in tqdm(messages, total=len(messages)):
            if message['user'] != user:
                continue
            try:
                client.chat_delete(channel=channel, ts=message['ts'])
                if 'files' in message:
                    for file in message['files']:
                        client.files_delete(file=file['id'])
                        time.sleep(1)  # Rate limit Tier 3 (50+/min)
            except slack.errors.SlackApiError as e:
                print(e)
            time.sleep(1)  # Rate limit Tier 3 (50+/min)


if __name__ == "__main__":
    main()
