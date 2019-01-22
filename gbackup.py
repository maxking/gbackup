#!/usr/bin/env python3
import configparser
import time
import logging
from pathlib import Path

import requests
import gitlab
import github

GITLAB_EXPORT_FINISHED_STATUS = 'finished'
EXPORT_WAIT_TIME = 2

log = logging.getLogger('gbackup')


def get_config_file():
    """Look for the Config file with auth details.

    A typical project config looks something like this::

        [gitlab.com]
        type = gitlab
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
    """Return an instance of gitlab.Gitlab with proper authentication creds.

    :param config: Configuration for Gitlab from config file.
    :type config: dict
    """
    return gitlab.Gitlab(
        config['server'],
        private_token=config['token'])


def gl_download_project(project, config, gl, section):
    """Download the backup of a project on to host.

    :param project: Project to download.
    :type project: gitlab.v4.objects.Project
    :param config: The configuration for Gitlab from config file.
    :type config: dict
    :param gl: An instance of gitlab.Gitlab API.
    :type gl: :class:`gitlab.Gitlab`
    :param section: The name of the section in config file this project belongs
        to. Used to generate the download path.
    :type section: str
    """
    project = gl.projects.get(project.id)
    export = project.exports.create({})
    # Wait for the finished status.
    export.refresh()
    while export.export_status != GITLAB_EXPORT_FINISHED_STATUS:
        time.sleep(EXPORT_WAIT_TIME)
        export.refresh()

    backup_path = Path(
        config.get('backup_dir', '~/.gitlab-backup'),
        section,
        project.path_with_namespace).expanduser()

    backup_path.mkdir(parents=True, exist_ok=True)

    backup_file = backup_path / time.strftime('%d-%b-%Y-%H-%M.tar.gz')

    log.info('Downloading backup for %s to %s', project.web_url, backup_file)

    with open(str(backup_file), 'wb') as fd:
        export.download(streamed=True, action=fd.write)


def gl_get_projects(gl, config):
    """Return a list of all the projects.

    This function looks at the config and returns all the projects of a user if
    `user` is specified and all the projects of a group if `group` is specified
    in the config.

    :param gl: An instance of Gitlab's API.
    :type gl: :class:`gitlab.Gitlab`
    :param config: Configuration for Gitlab from config gile.
    :type config: dict
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


def backup_gitlab(config, section):
    """Backup Gitlab projects.

    :param config: The configuration to backup gitlab projects.
    :type config: dict
    :param section: The name of the section to backup.
    :type section: str
    """
    gl = gl_get_instance(config)
    for project in gl_get_projects(gl, config):
        gl_download_project(project, config, gl, section)


def get_gh_instance(config):
    """Return an instance of Github.

    :param config: The Github configuration from config file.
    :type config: dict
    """
    if config.get('server'):
        return github.Github(
            base_url=config.get('server', 'https://github.com/api/v3'),
            login_or_token=config['access_token'])
    else:
        return github.Github(config['access_token'])


def gh_user_migration(project, gh, config, section):
    user = gh.get_user()
    log.info('Backing up repo %s for user %s at %s',
             project, user.name, section)
    migration = user.create_migration(repos=[project],
                                      lock_repositories=False)
    status = migration.get_status()
    while status in ('pending', 'exporting'):
        # Technically, this is wrong because of TOCTOU bug, but I am not much
        # worried about the attacks that can happen here. At worst, this can
        # fail to backup.
        time.sleep(EXPORT_WAIT_TIME)
        status = migration.get_status()

    try:
        if status == 'failed':
            log.error('Backup of [%s] for [%s] failed.', project, section)
            return
        assert status == 'exported', 'Unexpected status {}'.format(status)
        archive_url = migration.get_archive_url()
        backup_path = Path(
            config.get('backup_dir', '~/.github-backup'),
            section,
            user.login,
            project).expanduser()

        backup_path.mkdir(parents=True, exist_ok=True)

        backup_file = backup_path / time.strftime('%d-%b-%Y-%H-%M.tar.gz')

        with backup_file.open('wb+') as fd:
            raw_tar = requests.get(archive_url)
            fd.write(raw_tar.content)
    except Exception as e:
        log.error('Failed to backup %s due to %s', project, e)


def backup_github(config, section):
    """Backup Github projects.

    :param config: The configuration to backup Github projects.
    :type config: dict
    :param section: The name of the section to backup.
    :type section: str
    """
    gh = get_gh_instance(config)
    if 'user' in config:
        projects = [project.name
                    for project in gh.get_user().get_repos()]
        for project in projects:
            gh_user_migration(project, gh, config, section)


def main():
    """Download all the projects."""
    config = get_config()
    # If there is no config file, exit.
    if not config:
        log.error('No config file. Exiting.')
        exit(1)
    SECTION_TO_UTILITY = {
        'gitlab': backup_gitlab,
        'github': backup_github,
    }
    # Run backup of each website.
    for section_name in config.sections():
        section = config[section_name]
        if section['type'] not in SECTION_TO_UTILITY:
            log.error('Unsupported section [%s] in config', section_name)
            continue
        # Run the actual backup.
        log.info('Backing up %s', section_name)
        try:
            SECTION_TO_UTILITY[section['type']](section, section_name)
        except Exception as e:
            log.error('Failed to backup [%s] because of: %s', section_name, e)



if __name__ == '__main__':
    main()
