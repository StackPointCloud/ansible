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
module: oneandone_ssh_key
short_description: Configure 1&1 SSH keys.
description:
     - Create, update, and remove SSH keys.
       This module has a dependency on 1and1 >= 1.0
version_added: "2.5"
options:
  state:
    description:
      - Define a SSH key state to create, remove, or update.
    required: false
    default: 'present'
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
  ssh_key:
    description:
      The identifier (id or name) of the SSH key used with update state.
    required: true
  name:
    description:
      - SSH Key name. maxLength=128
    required: true
  description:
    description:
      - SSH Key description. maxLength=256
    required: false
  public_key:
    description:
      - Public key to import. If not given, new SSH key pair will be created
        and the private key is returned in the response.
    required: false
  ssh_key_id:
    description:
      - The ID of the SSH key used with absent state.
    required: true
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
  - Amel Ajdinovic (@aajdinov)
'''

EXAMPLES = '''

# Create an SSH key.

- oneandone_ssh_key:
    auth_token: oneandone_private_api_key
    name: My SSH Key
    description: My SSH description
    public_key: ssh-rsa AAAAB3NzbD...Zasx== your@email.com

# Update an SSH key.

- oneandone_ssh_key:
    auth_token: oneandone_private_api_key
    ssh_key: My SSH Key
    name: My SSH Key updated
    description: My SSH description updated
    state: update


# Delete an SSH key

- oneandone_ssh_key:
    auth_token: oneandone_private_api_key
    ssh_key_id: SSH key id
    state: absent

'''

RETURN = '''
ssh_key:
    description: Information about the SSH key that was processed
    type: dict
    sample: '{"id": "F77CC589EBC120905B4F4719217BFF6D", "name": "My SSH key"}'
    returned: always
'''

import os
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.oneandone import (
    get_datacenter,
    get_ssh_key,
    OneAndOneResources,
    wait_for_resource_creation_completion
)

HAS_ONEANDONE_SDK = True

try:
    import oneandone.client
except ImportError:
    HAS_ONEANDONE_SDK = False

DATACENTERS = ['US', 'ES', 'DE', 'GB']

TYPES = ['IPV4', 'IPV6']


def _check_mode(module, result):
    if module.check_mode:
        module.exit_json(
            changed=result
        )


def create_ssh_key(module, oneandone_conn):
    """
    Create a new SSH key

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object

    Returns a dictionary containing a 'changed' attribute indicating whether
    any SSH key was added.
    """
    name = module.params.get('name')
    description = module.params.get('description')
    public_key = module.params.get('public_key')
    wait = module.params.get('wait')
    wait_timeout = module.params.get('wait_timeout')
    wait_interval = module.params.get('wait_interval')

    try:
        _check_mode(module, name)
        ssh_key = oneandone_conn.create_ssh_key(
            ssh_key=oneandone.client.SshKey(
                name=name,
                description=description,
                public_key=public_key
            ))

        if wait:
            wait_for_resource_creation_completion(oneandone_conn,
                                                  OneAndOneResources.ssh_key,
                                                  ssh_key['id'],
                                                  wait_timeout,
                                                  wait_interval)
            ssh_key = oneandone_conn.get_ssh_key(ssh_key['id'])

        changed = True if ssh_key else False

        return (changed, ssh_key)
    except Exception as e:
        module.fail_json(msg=str(e))


def update_ssh_key(module, oneandone_conn):
    """
    Update an SSH key

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object

    Returns a dictionary containing a 'changed' attribute indicating whether
    any SSH key was changed.
    """
    ssh_key_id = module.params.get('ssh_key')
    name = module.params.get('name')
    description = module.params.get('description')
    wait = module.params.get('wait')
    wait_timeout = module.params.get('wait_timeout')
    wait_interval = module.params.get('wait_interval')

    ssh_key = get_ssh_key(oneandone_conn, ssh_key_id, True)
    if ssh_key is None:
        _check_mode(module, False)
        module.fail_json(
            msg='SSH key %s not found.' % ssh_key_id)

    try:
        _check_mode(module, True)
        ssh_key = oneandone_conn.modify_ssh_key(
            ssh_key_id=ssh_key['id'],
            name=name,
            description=description)

        if wait:
            wait_for_resource_creation_completion(oneandone_conn,
                                                  OneAndOneResources.ssh_key,
                                                  ssh_key['id'],
                                                  wait_timeout,
                                                  wait_interval)
            ssh_key = oneandone_conn.get_ssh_key(ssh_key['id'])

        changed = True if ssh_key else False

        return (changed, ssh_key)
    except Exception as e:
        module.fail_json(msg=str(e))


def delete_ssh_key(module, oneandone_conn):
    """
    Delete an SSH key

    module : AnsibleModule object
    oneandone_conn: authenticated oneandone object

    Returns a dictionary containing a 'changed' attribute indicating whether
    any SSH key was deleted.
    """
    ssh_key_id = module.params.get('ssh_key_id')

    ssh_key = get_ssh_key(oneandone_conn, ssh_key_id, True)
    if ssh_key is None:
        _check_mode(module, False)
        module.fail_json(
            msg='SSH key %s not found.' % ssh_key_id)

    try:
        _check_mode(module, True)
        deleted_ssh_key = oneandone_conn.delete_ssh_key(
            ssh_key_id=ssh_key['id'])

        changed = True if deleted_ssh_key else False

        return (changed, {
            'id': deleted_ssh_key['id'],
            'name': deleted_ssh_key['name']
        })
    except Exception as e:
        module.fail_json(msg=str(e))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            auth_token=dict(
                type='str',
                default=os.environ.get('ONEANDONE_AUTH_TOKEN')),
            api_url=dict(
                type='str',
                default=os.environ.get('ONEANDONE_API_URL')),
            ssh_key_id=dict(type='str'),
            name=dict(type='str'),
            description=dict(type='str'),
            public_key=dict(type='str'),
            ssh_key=dict(type='str'),
            wait=dict(type='bool', default=True),
            wait_timeout=dict(type='int', default=600),
            wait_interval=dict(type='int', default=5),
            state=dict(type='str', default='present', choices=['present', 'absent', 'update']),
        ),
        supports_check_mode=True
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
        if not module.params.get('ssh_key_id'):
            module.fail_json(
                msg="'ssh_key_id' parameter is required to delete a SSH key.")
        try:
            (changed, ssh_key) = delete_ssh_key(module, oneandone_conn)
        except Exception as e:
            module.fail_json(msg=str(e))
    elif state == 'update':
        if not module.params.get('ssh_key_id'):
            module.fail_json(
                msg="'ssh_key_id' parameter is required to update a SSH key.")
        try:
            (changed, ssh_key) = update_ssh_key(module, oneandone_conn)
        except Exception as e:
            module.fail_json(msg=str(e))

    elif state == 'present':
        try:
            (changed, ssh_key) = create_ssh_key(module, oneandone_conn)
        except Exception as e:
            module.fail_json(msg=str(e))

    module.exit_json(changed=changed, ssh_key=ssh_key)


if __name__ == '__main__':
    main()
