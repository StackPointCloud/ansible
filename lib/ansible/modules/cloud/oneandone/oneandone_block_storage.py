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
module: oneandone_block_storage
short_description: Configure 1&1 block storage.
description:
     - Create, remove, update block storages
       (and attach/detach to/from servers).
       This module has a dependency on 1and1 >= 1.5
version_added: "2.5"
options:
  state:
    description:
      - Define a block storage's state to create, remove, update.
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
      - Block storage name used with present state. Used as identifier (id or name) when used with absent state.
        maxLength=128
    required: true
  block_storage:
    description:
      - The identifier (id or name) of the block storage used with update state.
    required: true
  description:
    description:
      - Block storage description. maxLength=256
    required: false
  size:
    description:
      - Block storage size. min=20, max=500, multipleOf=10
    required: true
  datacenter_id:
    description:
      - ID of the datacenter where the shared storage will be created.
    required: false
  server_id:
    description:
      - ID of the server that the block storage will be attached to.
    required: false
  attach:
    description:
      - Used with update state. Indicates that the block storage should be attached to a server.
        server_id must be provided as well.
    required: false
  detach:
    description:
      - Used with update state. Indicates that the block storage should be detached from the server.
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

# Provisioning example. Create and destroy a block storage.

- oneandone_block_storage:
    auth_token: oneandone_private_api_key
    name: ansible block storage
    description: Testing creation of a block storage with ansible
    size: 20
    datacenter_id: DATACENTER_ID
    wait: true

- oneandone_block_storage:
    auth_token: oneandone_private_api_key
    state: absent
    name: ansible block storage

# Update a block storage.

- oneandone_block_storage:
    auth_token: oneandone_private_api_key
    block_storage: ansible block storage
    name: ansible block storage updated
    description: Testing creation of a block storage with ansible updated
    wait: true
    state: update

# Attach block storage to a server

- oneandone_block_storage:
    auth_token: oneandone_private_api_key
    block_storage: ansible block storage updated
    server_id: SERVER_ID
    attach: true
    wait: true
    state: update

# Detach a block storage from a server

- oneandone_block_storage:
    auth_token: oneandone_private_api_key
    block_storage: ansible block storage updated
    detach: true
    wait: true
    state: update
'''

RETURN = '''
block_storage:
    description: Information about the block storage that was processed
    type: dict
    sample: '{"id": "92B74394A397ECC3359825C1656D67A6", "name": "Default block storage "}'
    returned: always
'''

import os
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.oneandone import (
    get_block_storage,
    get_server,
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


def _attach_block_storage(module, oneandone_conn, block_storage_id, server_id):
    """
    Attaches a block storage to a server.
    """
    try:
        block_storage = oneandone_conn.attach_block_storage(
            block_storage_id=block_storage_id,
            server_id=server_id)
        return block_storage
    except Exception as ex:
        module.fail_json(msg=str(ex))


def _detach_block_storage(module, oneandone_conn, block_storage_id):
    """
    Detaches a server from a block storage.
    """
    try:
        block_storage = oneandone_conn.detach_block_storage(
            block_storage_id=block_storage_id)
        return block_storage
    except Exception as ex:
        module.fail_json(msg=str(ex))


def update_block_storage(module, oneandone_conn):
    """
    Updates a block_storage based on input arguments.
    Block storage ports, processes and servers can be added/removed to/from
    a block storage. Block storage name, description, email,
    thresholds for cpu, ram, disk, transfer and internal_ping
    can be updated as well.

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object
    """
    try:
        block_storage_id = module.params.get('block_storage')
        name = module.params.get('name')
        description = module.params.get('description')
        server_id = module.params.get('server_id')
        attach = module.params.get('attach')
        detach = module.params.get('detach')

        changed = False

        block_storage = get_block_storage(oneandone_conn, block_storage_id, True)
        if block_storage is None:
            _check_mode(module, False)

        if name or description:
            _check_mode(module, True)
            block_storage = oneandone_conn.modify_block_storage(
                block_storage_id=block_storage['id'],
                name=name,
                description=description)
            changed = True

        if attach:
            if module.check_mode:
                server = get_server(oneandone_conn, server_id)
                _check_mode(module, server)

            block_storage = _attach_block_storage(module,
                                                  oneandone_conn,
                                                  block_storage['id'],
                                                  server_id)
            changed = True

        if detach:
            _check_mode(module, True)

            _detach_block_storage(module,
                                  oneandone_conn,
                                  block_storage['id'])
            _check_mode(module, False)
            block_storage = get_block_storage(oneandone_conn, block_storage['id'], True)
            changed = True

        return (changed, block_storage)
    except Exception as ex:
        module.fail_json(msg=str(ex))


def create_block_storage(module, oneandone_conn):
    """
    Creates a new block storage.

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object
    """
    try:
        name = module.params.get('name')
        description = module.params.get('description')
        size = module.params.get('size')
        server_id = module.params.get('server_id')
        datacenter_id = module.params.get('datacenter_id')
        wait = module.params.get('wait')
        wait_timeout = module.params.get('wait_timeout')
        wait_interval = module.params.get('wait_interval')

        _block_storage = oneandone.client.BlockStorage(name,
                                                       description,
                                                       size,
                                                       datacenter_id,
                                                       server_id)

        _check_mode(module, True)
        block_storage = oneandone_conn.create_block_storage(
            block_storage=_block_storage
        )

        if wait:
            wait_for_resource_creation_completion(
                oneandone_conn,
                OneAndOneResources.block_storage,
                block_storage['id'],
                wait_timeout,
                wait_interval)

        changed = True if block_storage else False

        _check_mode(module, False)

        return (changed, block_storage)
    except Exception as ex:
        module.fail_json(msg=str(ex))


def remove_block_storage(module, oneandone_conn):
    """
    Removes a block storage.

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object
    """
    try:
        blkst_id = module.params.get('name')
        block_storage_id = get_block_storage(oneandone_conn, blkst_id)
        if module.check_mode:
            if block_storage_id is None:
                _check_mode(module, False)
            _check_mode(module, True)
        block_storage = oneandone_conn.delete_block_storage(block_storage_id)

        changed = True if block_storage else False

        return (changed, {
            'id': block_storage['id'],
            'name': block_storage['name']
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
            block_storage=dict(type='str'),
            description=dict(type='str'),
            size=dict(type='int'),
            datacenter_id=dict(type='str'),
            server_id=dict(type='str'),
            attach=dict(type='bool', default=False),
            detach=dict(type='bool', default=False),
            wait=dict(type='bool', default=True),
            wait_timeout=dict(type='int', default=600),
            wait_interval=dict(type='int', default=5),
            state=dict(type='str', default='present', choices=['present', 'absent', 'update']),
        ),
        supports_check_mode=True,
        mutually_exclusive=(['attach', 'detach'],),
        required_together=(['attach', 'server_id'],)
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
                msg="'name' parameter is required to delete a block storage.")
        try:
            (changed, block_storage) = remove_block_storage(module, oneandone_conn)
        except Exception as ex:
            module.fail_json(msg=str(ex))
    elif state == 'update':
        if not module.params.get('block_storage'):
            module.fail_json(
                msg="'block_storage' parameter is required to update a block storage.")
        try:
            (changed, block_storage) = update_block_storage(module, oneandone_conn)
        except Exception as ex:
            module.fail_json(msg=str(ex))
    elif state == 'present':
        for param in ('name', 'size'):
            if not module.params.get(param):
                module.fail_json(
                    msg="%s parameter is required for a new block storage." % param)
        try:
            (changed, block_storage) = create_block_storage(module, oneandone_conn)
        except Exception as ex:
            module.fail_json(msg=str(ex))

    module.exit_json(changed=changed, block_storage=block_storage)


if __name__ == '__main__':
    main()
