glbackup
==========

A utility to backup all [Gitlab](https://gitlab.com) projects of a user or group.

# Requirements

This requires `python-gitlab` package and requires Python 3.5+.

# Setup

These setup requirements will setup a python
[virtualenv](https://virtualenv.pypa.io/en/latest/) to run the script which
backs up all your projects.

First, setup a config file with your access credentials:

```
# ~/.glbackup.ini
[main]
server = https://gitlab.com
token = <access-token>
group = <gitlab-group>
user = <gitlab-username>
backup_dir = ~/.gitlab-backup
```

Now, let's setup [virtualenv]((https://virtualenv.pypa.io/en/latest/)) and start
backup.

```bash
$ git clone https://github.com/maxking/glbackup
$ cd glbackup
$ python3 -m venv gitlab
$ source gitlab/bin/activate
(gitlab)$ pip install python-gitlab
```

Finally, to start the backup, run the `glbackup.py` script.

```
$ ./glbackup.py
Downloading backup for https://gitlab.com/maxking/mailman to /home/maxking/.gitlab-backup/maxking/mailman/11-Jan-2019-19-53.tar.gz
```

