#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: oneandone_shared_storage
short_description: Configure 1&1 shared storage.
description:
     - Create, remove, update shared storages
       (and attach/detach to/from servers).
       This module has a dependency on 1and1 >= 1.5
version_added: "2.5"
options:
  state:
    description:
      - Define a shared storage's state to create, remove, update.
    required: false
    default: present
    choices: [ "present", "absent", "update" ]
  auth_token:
    description:
      - Authenticating API token provided by 1&1.
    required: true
  api_url:
    description:
      - Custom API URL. Overrides the
        ONEANDONE_API_URL environement variable.
    required: false
  name:
    description:
      - Shared storage name used with present state. Used as identifier (id or name) when used with absent state.
        maxLength=128
    required: true
  shared_storage:
    description:
      - The identifier (id or name) of the shared storage used with update state.
    required: true
  description:
    description:
      - Shared storage description. maxLength=256
    required: false
  size:
    description:
      - Shared storage size. min=50, max=2000, multipleOf=50
    required: true
  datacenter_id:
    description:
      - ID of the datacenter where the shared storage will be created.
    required: false
  servers:
    description:
      - List of servers to which the shared storage will be attached to.
    required: false
    suboptions:
      id:
        description:
          - ID of the server.
        required: true
      rights:
        description:
          - Rights for accessing from servers. (R, RW)
        required: true
        choices: [ "R", "RW" ]
  server_id:
    description:
      - ID of the server to detach.
    required: false
  password:
    description:
      - New user pass for accessing to storages. Pass must contain at least
        8 characters using uppercase letters, numbers and other special symbols.
    required: false
  attach:
    description:
      - Used with update state. Indicates that the shared storage should be attached to the provided
        servers. servers must be provided.
    required: false
  detach:
    description:
      - Used with update state. Indicates that the shared storage should be detached from the server.
    required: false
  wait:
    description:
      - wait for the instance to be in state 'running' before returning
    required: false
    default: "yes"
    choices: [ "yes", "no" ]
  wait_timeout:
    description:
      - how long before wait gives up, in seconds
    default: 600
  wait_interval:
    description:
      - Defines the number of seconds to wait when using the _wait_for methods
    default: 5

requirements:
  - "1and1"
  - "python >= 2.6"

author:
  -  "Amel Ajdinovic (@aajdinov)"
'''

EXAMPLES = '''

# Provisioning example. Create and destroy a shared storage.

- oneandone_shared_storage:
    auth_token: oneandone_private_api_key
    name: ansible shared storage
    description: Testing creation of a shared storage with ansible
    size: 50
    datacenter_id: DATACENTER_ID
    wait: true

- oneandone_shared_storage:
    auth_token: oneandone_private_api_key
    state: absent
    name: ansible shared storage

# Update a shared storage.

- oneandone_shared_storage:
    auth_token: oneandone_private_api_key
    shared_storage: ansible shared storage
    name: ansible shared storage updated
    description: Testing creation of a shared storage with ansible updated
    size: 100
    wait: true
    state: update

# Attach shared storage to a list of servers

- oneandone_shared_storage:
    auth_token: oneandone_private_api_key
    shared_storage: ansible shared storage updated
    servers:
     -
       id: server_id_1
       rights: R
     -
       id: server_id_2
       rights: RW
    attach: true
    wait: true
    state: update

# Detach a shared storage from a server

- oneandone_shared_storage:
    auth_token: oneandone_private_api_key
    shared_storage: ansible shared storage updated
    server_id: server_id_1
    detach: true
    wait: true
    state: update

# Change the password for accessing the shared storages

- oneandone_shared_storage:
    auth_token: oneandone_private_api_key
    password: neW_Pa$$word
    wait: true
    state: update
'''

RETURN = '''
shared_storage:
    description: Information about the shared storage that was processed
    type: dict
    sample: '{"id": "92B74394A397ECC3359825C1656D67A6", "name": "Default shared storage "}'
    returned: always
'''

import os
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.oneandone import (
    get_shared_storage,
    get_shared_storage_server,
    OneAndOneResources,
    wait_for_resource_creation_completion
)

HAS_ONEANDONE_SDK = True

try:
    import oneandone.client
except ImportError:
    HAS_ONEANDONE_SDK = False


def _check_mode(module, result):
    if module.check_mode:
        module.exit_json(
            changed=result
        )


def _attach_shared_storage(module, oneandone_conn, shared_storage_id, servers):
    """
    Attaches a shared storage to the provided servers.
    """
    try:
        shared_storage = oneandone_conn.attach_server_shared_storage(
            shared_storage_id=shared_storage_id,
            server_ids=servers)
        return shared_storage
    except Exception as ex:
        module.fail_json(msg=str(ex))


def _detach_shared_storage(module, oneandone_conn, shared_storage_id, server_id):
    """
    Detaches a shared storage from a server.
    """
    try:
        shared_storage = oneandone_conn.detach_server_shared_storage(
            shared_storage_id=shared_storage_id,
            server_id=server_id)
        return shared_storage
    except Exception as ex:
        module.fail_json(msg=str(ex))


def update_shared_storage(module, oneandone_conn):
    """
    Updates a shared_storage based on input arguments.
    Shared storages can be attached/detached to/from
    servers. Shared storage name, description, and size
    can be updated, as well as password for accessing
    shared storages.

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object
    """
    try:
        shared_storage_id = module.params.get('shared_storage')
        name = module.params.get('name')
        description = module.params.get('description')
        size = module.params.get('size')
        servers = module.params.get('servers')
        server_id = module.params.get('server_id')
        password = module.params.get('password')
        attach = module.params.get('attach')
        detach = module.params.get('detach')

        changed = False

        shared_storage = get_shared_storage(oneandone_conn, shared_storage_id, True)
        if shared_storage is None:
            _check_mode(module, False)

        if name or description or size:
            _check_mode(module, True)
            shared_storage = oneandone_conn.modify_shared_storage(
                shared_storage_id=shared_storage['id'],
                name=name,
                description=description,
                size=size)
            changed = True

        if password:
            _check_mode(module, True)
            shared_storage = oneandone_conn.change_password(password)
            changed = True
        if attach:
            if module.check_mode:
                _check_mode(module, servers)

            shared_storage = _attach_shared_storage(module,
                                                    oneandone_conn,
                                                    shared_storage['id'],
                                                    servers)
            changed = True

        if detach:
            if module.check_mode:
                ss_server = get_shared_storage_server(oneandone_conn, shared_storage, server_id)
                _check_mode(module, ss_server)

            _detach_shared_storage(module,
                                  oneandone_conn,
                                  shared_storage['id'])
            _check_mode(module, False)
            shared_storage = get_shared_storage(oneandone_conn, shared_storage['id'], True)
            changed = True

        return (changed, shared_storage)
    except Exception as ex:
        module.fail_json(msg=str(ex))


def create_shared_storage(module, oneandone_conn):
    """
    Creates a new shared storage.

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object
    """
    try:
        name = module.params.get('name')
        description = module.params.get('description')
        size = module.params.get('size')
        datacenter_id = module.params.get('datacenter_id')
        wait = module.params.get('wait')
        wait_timeout = module.params.get('wait_timeout')
        wait_interval = module.params.get('wait_interval')

        _shared_storage = oneandone.client.SharedStorage(name,
                                                         description,
                                                         size,
                                                         datacenter_id)

        _check_mode(module, True)
        shared_storage = oneandone_conn.create_shared_storage(
            shared_storage=_shared_storage
        )

        if wait:
            wait_for_resource_creation_completion(
                oneandone_conn,
                OneAndOneResources.shared_storage,
                shared_storage['id'],
                wait_timeout,
                wait_interval)

        changed = True if shared_storage else False

        _check_mode(module, False)

        return (changed, shared_storage)
    except Exception as ex:
        module.fail_json(msg=str(ex))


def remove_shared_storage(module, oneandone_conn):
    """
    Removes a shared storage.

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object
    """
    try:
        ss_id = module.params.get('name')
        shared_storage_id = get_shared_storage(oneandone_conn, ss_id)
        if module.check_mode:
            if shared_storage_id is None:
                _check_mode(module, False)
            _check_mode(module, True)
        shared_storage = oneandone_conn.delete_shared_storage(shared_storage_id)

        changed = True if shared_storage else False

        return (changed, {
            'id': shared_storage['id'],
            'name': shared_storage['name']
        })
    except Exception as ex:
        module.fail_json(msg=str(ex))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            auth_token=dict(
                type='str',
                default=os.environ.get('ONEANDONE_AUTH_TOKEN')),
            api_url=dict(
                type='str',
                default=os.environ.get('ONEANDONE_API_URL')),
            name=dict(type='str'),
            shared_storage=dict(type='str'),
            description=dict(type='str'),
            size=dict(type='int'),
            datacenter_id=dict(type='str'),
            servers=dict(type='list', default=[]),
            server_id=dict(type='str'),
            password=dict(type='str'),
            attach=dict(type='bool', default=False),
            detach=dict(type='bool', default=False),
            wait=dict(type='bool', default=True),
            wait_timeout=dict(type='int', default=600),
            wait_interval=dict(type='int', default=5),
            state=dict(type='str', default='present', choices=['present', 'absent', 'update']),
        ),
        supports_check_mode=True,
        mutually_exclusive=(['attach', 'detach'],),
        required_together=(['attach', 'servers'], ['detach', 'server_id'],)
    )

    if not HAS_ONEANDONE_SDK:
        module.fail_json(msg='1and1 required for this module')

    if not module.params.get('auth_token'):
        module.fail_json(
            msg='auth_token parameter is required.')

    if not module.params.get('api_url'):
        oneandone_conn = oneandone.client.OneAndOneService(
            api_token=module.params.get('auth_token'))
    else:
        oneandone_conn = oneandone.client.OneAndOneService(
            api_token=module.params.get('auth_token'), api_url=module.params.get('api_url'))

    state = module.params.get('state')

    if state == 'absent':
        if not module.params.get('name'):
            module.fail_json(
                msg="'name' parameter is required to delete a shared storage.")
        try:
            (changed, shared_storage) = remove_shared_storage(module, oneandone_conn)
        except Exception as ex:
            module.fail_json(msg=str(ex))
    elif state == 'update':
        if not module.params.get('shared_storage'):
            module.fail_json(
                msg="'shared_storage' parameter is required to update a shared storage.")
        try:
            (changed, shared_storage) = update_shared_storage(module, oneandone_conn)
        except Exception as ex:
            module.fail_json(msg=str(ex))
    elif state == 'present':
        for param in ('name', 'size'):
            if not module.params.get(param):
                module.fail_json(
                    msg="%s parameter is required for a new shared storage." % param)
        try:
            (changed, shared_storage) = create_shared_storage(module, oneandone_conn)
        except Exception as ex:
            module.fail_json(msg=str(ex))

    module.exit_json(changed=changed, shared_storage=shared_storage)


if __name__ == '__main__':
    main()
