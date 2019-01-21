gbackup
==========

A utility to backup all [Gitlab](https://gitlab.com) projects of a user or
group. It can download projects of multiple groups and users.

# Requirements

This requires `python-gitlab` package and requires Python 3.5+.

# Setup

These setup requirements will setup a python
[virtualenv](https://virtualenv.pypa.io/en/latest/) to run the script which
backs up all your projects.

First, setup a config file with your access credentials. `user` and `group` are
optional, you can specify whichever one you want to backup.

```
# ~/.gbackup.ini
[main]
server = https://gitlab.com
token = <access-token>
group =
  <gitlab-group1>
  <gitlab-group2>
  <gitlab-group3>
user =
  <gitlab-username>
backup_dir = ~/.gitlab-backup
```

Now, let's setup [virtualenv]((https://virtualenv.pypa.io/en/latest/)) and start
backup.

```bash
$ git clone https://github.com/maxking/gbackup
$ cd glbackup
$ python3 -m venv gitlab
$ source gitlab/bin/activate
(gitlab)$ pip install python-gitlab
```

# Usage

Finally, to start the backup, run the `gbackup.py` script.

```
$ ./gbackup.py
Downloading backup for https://gitlab.com/maxking/mailman to /home/maxking/.gitlab-backup/maxking/mailman/11-Jan-2019-19-53.tar.gz
```

# License

All the contents of this repository is licensed under Apache License
v2.0. Please see the LICENSE file for complete license text.
