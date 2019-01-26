#! /usr/bin/env python

import asyncio
import aiohttp
import configparser
import logging
import time

from urllib.parse import urljoin
from pathlib import Path

log = logging.getLogger('gbackup-async')
# log.setLevel(logging.DEBUG)


# Gitlab API v4 base URL.
BASE_GITLAB_URL = 'https://gitlab.com/api/v4/'
# Time to sleep for waiting for project to be exported.
EXPORT_WAIT_TIME = 2
# Download chunk size.
CHUNK_SIZE = 1024

def get_config_file():
    """Look for the Config file with auth details.

    A typical project config looks something like this::

        [main]
        server = https://gitlab.com
        token = <persosonal-token>
        group =
          <group-name>
        user =
          <gitlab-username>
        backup_dir = ~/.gitlab-backup

    """
    default_config = Path(Path.home(), '.glbackup.ini')
    if default_config.exists():
        return default_config
    return None


def get_config(config_file=None):
    config_file = get_config_file()
    # First, let's see if there is a config file present.
    config = configparser.ConfigParser()
    config.read(str(config_file))
    if not 'main' in config:
        msg = 'No `main` section in config file {}'.format(config_file)
        raise ValueError(msg)
    return config['main']


def gitlab_url_builder(url, base_url=None):
    if not base_url:
        base_url = BASE_GITLAB_URL
    return urljoin(base_url, url)


def get_gitlab_session(access_token=None):
    headers = {}
    if access_token:
        headers = {'Private-Token': access_token}
    client_session = aiohttp.ClientSession(raise_for_status=False, headers=headers)
    return client_session


async def get_user_projects(session, user):
    url = gitlab_url_builder(f'users/{user}/projects?statistics=yes&per_page=100')
    print('GET: {}'.format(url))
    resp = await session.get(url)
    if resp.status == 200 and resp.headers.get('content-type') == 'application/json':
        projects = await resp.json()
        return projects
    else:
        print('Bad Response from Gitlab: ', end='')
        print(f'status={resp.status} content-type={resp.headers.get("content-type")}')
        print(f'Response {resp}')


async def start_gitlab_export(session, project_id, project_name):
    url = gitlab_url_builder(f'projects/{project_id}/export')
    resp = await session.post(url)
    # Triggering an export returns a status 202 Accepted.
    if resp.status == 202:
        print(f'Triggered export on project {project_name}')
        return True
    else:
        print(f'Unable to Trigger export for {project_name}')
        print(f'Response: {resp}')
        return False


async def check_export_status(session, project_id):
    url = gitlab_url_builder(f'projects/{project_id}/export')
    resp = await session.get(url)
    if resp.status == 200:
        export_status =  await resp.json()
        return export_status.get('export_status')
    else:
        print(f'Failed to check response status: {resp} for {project_id}')
        return None


async def download_gitlab_export(session, project_id, project_name, download_path):
    status = await check_export_status(session, project_id)
    while status != 'finished':
        await asyncio.sleep(EXPORT_WAIT_TIME)
        status = await check_export_status(session, project_id)
        if status is None:
            print(f'Unable to check status, not downloading {project_name}')
            return
    assert status == 'finished', 'Loop exited without finished exporting'
    # So now we have exported our project, let's download it.
    print(f'Downloading {project_name}')
    url = gitlab_url_builder(f'projects/{project_id}/export/download')
    resp = await session.get(url)
    if resp.status == 200:
        with open(download_path, 'wb') as fd:
            while True:
                chunk = await resp.content.read(CHUNK_SIZE)
                if not chunk:
                    break
                fd.write(chunk)
    else:
        print('Failed to download export of project {project_name}')
        print(f'Error response: {resp}')


def get_project_export_path(project, config):
    base_path = Path(config.get('backup_dir')).expanduser()
    project_path = base_path / project.get('path_with_namespace')
    project_path.mkdir(parents=True, exist_ok=True)
    return project_path / time.strftime('%d-%b-%Y-%H-%M.tar.gz')


async def main():
    config = get_config()
    gl = get_gitlab_session(access_token=config.get('token'))
    projects = await get_user_projects(gl, config['user'])
    migrations = []
    # Trigger all exports at once, so that we have them ready when we want to
    # download them, this optimizes the process a bit more, since we don't wait
    # as much for every single export since they are being exported while we
    # download the first one.
    # We trigger export in decreasing order of size and download then in
    # increasing order of size so that the largest project has the maximum time
    # to get exported.
    for project in sorted(projects, key=lambda x: x['statistics']['repository_size'], reverse=True):
        # Trigger an export for a project. If it was triggered correctly, add it
        # to migrations to download it later.
        if await start_gitlab_export(gl, project.get('id'), project.get('path_with_namespace')):
            migrations.append(project)
    # We reverse the order in which download because we triggered download in
    # decreasing order of size. We want to download the smallest project first
    # so that larger projects get more time to download.
    migrations.reverse()
    for project in migrations:
        export_path = get_project_export_path(project, config)
        await download_gitlab_export(
            gl, project.get('id'), project.get('path_with_namespace'), export_path)
    await gl.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
# Wait for a while to terminate SSL gracefully, recommended by aiohttp.
loop.run_until_complete(asyncio.sleep(0.250))
loop.close()
