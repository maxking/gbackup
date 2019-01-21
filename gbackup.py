#!/usr/bin/env python3
import configparser
import time
import logging
from pathlib import Path

import gitlab


GITLAB_EXPORT_FINISHED_STATUS = 'finished'
EXPORT_WAIT_TIME = 2

log = logging.getLogger('gbackup')


def get_config_file():
    """Look for the Config file with auth details.

    A typical project config looks something like this::

        [gitlab]
        server = https://gitlab.com
        token = <persosonal-token>
        group =
          <group-name>
        user =
          <gitlab-username>
        backup_dir = ~/.gitlab-backup

    """
    default_config = Path(Path.home(), '.gbackup.ini')
    if default_config.exists():
        return default_config
    return None


def get_config():
    """Return a config object."""
    config_file = get_config_file()
    if not config_file:
        return None
    # First, let's see if there is a config file present.
    config = configparser.ConfigParser()
    config.read(str(config_file))
    return config


def gl_get_instance(config):
    """Return an instance of gitlab.Gitlab with proper authentication"""
    return gitlab.Gitlab(
        config['server'],
        private_token=config['token'])


def gl_download_project(project, config, gl):
    """Download the backup of a project on to host."""
    project = gl.projects.get(project.id)
    export = project.exports.create({})
    # Wait for the finished status.
    export.refresh()
    while export.export_status != GITLAB_EXPORT_FINISHED_STATUS:
        time.sleep(EXPORT_WAIT_TIME)
        export.refresh()

    backup_path = Path(
        config.get('backup_dir', '~/.gitlab-backup'),
        project.path_with_namespace)
    backup_path.expanduser()
    backup_path.mkdir(parents=True, exist_ok=True)

    backup_file = backup_path / time.strftime('%d-%b-%Y-%H-%M.tar.gz')

    log.info('Downloading backup for %s to %s',
             project.web_url, backup_file)
    with open(str(backup_file), 'wb') as fd:
        export.download(streamed=True, action=fd.write)


def gl_get_projects(gl, config):
    """Return a list of all the projects.

    This function looks at the config and returns all the projects of a user if
    `user` is specified and all the projects of a group if `group` is specified
    in the config.
    """
    projects = []
    if 'group' in config:
        for group_name in config['group'].split():
            group = gl.groups.get(group_name)
            projects.extend(group.projects.list())
    if 'user' in config:
        for username in config['user'].split():
            user = gl.users.list(username=username)[0]
            projects.extend(user.projects.list())
    return projects


def backup_gitlab(config):
    """Backup Gitlab projects."""
    gl = gl_get_instance(config)
    for project in gl_get_projects(gl, config):
        gl_download_project(project, config, gl)


def main():
    """Download all the projects."""
    config = get_config()
    # If there is no config file, exit.
    if not config:
        log.error('No config file. Exiting.')
        exit(1)
    SECTION_TO_UTILITY = {
        'gitlab': backup_gitlab,
    }
    # Run backup of each website.
    for section in config.sections():
        if section not in SECTION_TO_UTILITY:
            log.error('Unsupported section [%s] in config', section)
        # Run the actual backup.
        log.info('Backing up %s', section)
        try:
            SECTION_TO_UTILITY[section](config[section])
        except Exception as e:
            log.error('Failed to backup [%s] because of: %s', section, e)


if __name__ == '__main__':
    main()
