#!/usr/bin/env python3
import configparser
import time
from pathlib import Path

import gitlab

EXPORT_FINISHED_STATUS = 'finished'


def get_config_file():
    """Look for the Config file with auth details.

    A typical project config looks something like this::

        [main]
        server = https://gitlab.com
        token = <persosonal-token>
        group = <group-name>
        user = <gitlab-username>
        backup_dir = ~/.gitlab-backup

    """
    default_config = Path(Path.home(), '.glbackup.ini')
    if default_config.exists():
        return default_config
    return None


def get_config():
    """Return a config object."""
    config_file = get_config_file()
    # First, let's see if there is a config file present.
    config = configparser.ConfigParser()
    config.read(config_file)
    if not 'main' in config:
        msg = 'No `main` section in config file {}'.format(config_file)
        raise ValueError(msg)
    return config['main']


def get_gitlab_instance(config):
    """Return an instance of gitlab.Gitlab with proper authentication"""
    gl = gitlab.Gitlab(config['server'],
                       private_token=config['token'])
    return gl


def download_project(project, config, gl):
    """Download the backup of a project on to host."""
    project = gl.projects.get(project.id)
    export = project.exports.create({})
    # Wait for the finished status.
    export.refresh()
    while export.export_status != EXPORT_FINISHED_STATUS:
        time.sleep(2)
        export.refresh()

    backup_path = Path(
        config['backup_dir'],
        project.path_with_namespace).expanduser()
    backup_path.mkdir(parents=True, exist_ok=True)

    backup_file = backup_path / time.strftime('%d-%b-%Y-%H-%M.tar.gz')

    print('Downloading backup for {0} to {1}'.format(
        project.web_url, backup_file))
    with open(backup_file, 'wb') as fd:
        export.download(streamed=True, action=fd.write)


def get_projects(gl, config):
    """Return a list of all the projects.

    This function looks at the config and returns all the projects of a user if
    `user` is specified and all the projects of a group if `group` is specified
    in the config.
    """
    projects = []
    if 'group' in config:
        mm_group = gl.groups.get(config['group'])
        projects.extend(mm_group.projects.list())
    if 'user' in config:
        user = gl.users.list(username=config['user'])
        projects.extend(user.projects.list())
    return projects


def main():
    """Download all the projects."""
    config = get_config()
    gl = get_gitlab_instance(config)
    for project in get_projects(gl, config):
        download_project(project, config, gl)


if __name__ == '__main__':
    main()
