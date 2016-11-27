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

DOCUMENTATION = '''
---
module: ecs_cluster_facts
short_description: list ECS clusters
notes:
    - for details of the parameters and returns see (http://boto3.readthedocs.org/en/latest/reference/services/ecs.html)
description:
    - Lists ECS clusters.
version_added: "2.1"
author:
    - "Luca Agostini (@lucaagostini)"
requirements: [ json, boto, botocore, boto3 ]
options:
    name:
        description:
            - Search the cluster with name that matches this string.
        required: false
        default: ''
    search_mode:
        description:
            - The mode to use to match the cluster name:
              if 'substring' it searches the name parameter as substring of the cluster name,
              if 'exact' it searches the name parameter with exact match of the cluster name,
              if 'regex' it searches the name parameter considering it as a regular expression  
        required: false
        default: 'substring'
        choices: ['substring', 'exact', 'refex']
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# List all clusters
- ecs_cluster_facts:

# List all cluster matches the regular expression
- ecs_cluster_facts:
    name: MYCLUSTER-.*
    search_mode: regex

# Get the cluster details with the exact name
- ecs_cluster_facts:
    name: MYCLUSTER
    search_mode: exact
'''

RETURN = '''
clusters:
    description: Returns an array of complex objects as described below.
    returned: success
    type: list of complex
    contains:
        activeServicesCount:
            description: The number of services that are running on the cluster in an ACTIVE state. You can view these services with ListServices .
            returned: always
            type: int
        clusterArn:
            description: The Amazon Resource Name (ARN) that identifies the cluster.
            returned: always
            type: string
        clusterName:
            description: A user-generated string that you use to identify your cluster.
            returned: always
            type: string
        pendingTasksCount:
            description: The number of tasks in the cluster that are in the PENDING state.
            returned: always
            type: int
        registeredContainerInstancesCount:
            description: The number of container instances registered into the cluster.
            returned: always
            type: int
        runningTasksCount:
            description: The number of tasks in the cluster that are in the RUNNING state.
            returned: always
            type: int
        status:
            description: The status of the cluster. The valid values are ACTIVE or INACTIVE . ACTIVE indicates that you can register container instances with the cluster and the associated instances can accept tasks.
            returned: always
            type: string
'''
import re
import time

try:
    import boto
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

class EcsClusterManager:
    """Handles ECS Clusters"""

    def __init__(self, module):
        self.module = module

        try:
            # self.ecs = boto3.client('ecs')
            region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
            if not region:
                module.fail_json(msg="Region must be specified as a parameter, in EC2_REGION or AWS_REGION environment variables or in boto configuration file")
            self.ecs = boto3_conn(module, conn_type='client', resource='ecs', region=region, endpoint=ec2_url, **aws_connect_kwargs)
        except boto.exception.NoAuthHandlerFound, e:
            self.module.fail_json(msg="Can't authorize connection - "+str(e))

    def list_clusters(self):
        cluster_arns = []
        response = self.ecs.list_clusters()
        cluster_arns += response['clusterArns']
        if 'nextToken' in response:
            response_next_token = response['nextToken']
            while response_next_token is not None:
                response = self.ecs_list_clusters()
                cluster_arns += response['clusterArns']
                if 'nextToken' in response:
                    response_next_token = response['nextToken']
                else:
                    response_next_token = None
        return cluster_arns

    def describe_clusters(self, cluster_arns):
        cluster_details = []
        cluster_max_size = 50
        while len(cluster_arns) > 0:
            response = self.ecs.describe_clusters(clusters=cluster_arns[0:cluster_max_size])
            if len(response['clusters'])>0:
                cluster_details += response['clusters']
            else:
              raise Exception("Unknown problem describing cluster %s." % cluster_arns)
            cluster_arns = cluster_arns[cluster_max_size:]
        return cluster_details


    def filter_clusters(self, clusters, filter_param, filter_value, filter_mode):
        filtered_clusters = []
        for cluster in clusters:
            if filter_mode == 'substring':
                if filter_value in cluster[filter_param]:
                    filtered_clusters.append(cluster)
            elif filter_mode == 'exact':
                if cluster[filter_param] == filter_value:
                    filtered_clusters.append(cluster)
            elif filter_mode == 'regex':
                if re.match(r'%s' % filter_value, cluster[filter_param]):
                    filtered_clusters.append(cluster)
        return filtered_clusters

def main():

    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        name=dict(default='', required=False, type='str' ),
        search_mode=dict(default='substring', choices=['substring', 'exact', 'regex']),
    ))
    required_together = ( ['state', 'name'] )
    results = dict(changed=False)

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True, required_together=required_together)

    if not HAS_BOTO:
        module.fail_json(msg='boto is required.')

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 is required.')

    cluster_mgr = EcsClusterManager(module)
    try:
        cluster_arns = cluster_mgr.list_clusters()
        cluster_details = cluster_mgr.describe_clusters(cluster_arns)
        cluster_filtered = cluster_mgr.filter_clusters(cluster_details, 'clusterName', module.params['name'], module.params['search_mode'])
        results['clusters'] = cluster_filtered
    except Exception, e:
        module.fail_json(msg="Exception describing cluster '"+module.params['name']+"': "+str(e))

    module.exit_json(**results)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
