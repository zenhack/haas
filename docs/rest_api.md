This file documents the HaaS REST API in detail.

# How to read

Each possible API call has an entry below containing:

* an HTTP method and URL path, including possible `<parameters>` in the
  path to be treated as arguments.
* Optionally, a summary of the request body (which will always be a JSON
  object).
* A human readable description of the semantics of the call
* A summary of the response body for a successful request. Many calls do
  not return any data, in which case this is omitted.
* Any authorization requirements, which could include:
  * Administrative access
  * Access to a particular project or
  * No special access
 In general, administrative access is sufficient to perform any action.
* A list of possible errors.

In addition to the error codes listed for each API call, HaaS may
return:

* 400 if something is wrong with the request (e.g. malformed request
  body)
* 401 if the user does not have permission to execute the supplied
  request.
* 404 if the api call references an object that does not exist
  (obviously, this is acceptable for calls that create the resource).

Below is an example.

# my_api_call

`POST /url/path/to/<thing>`

Request Body:

    {
        "some_field": "a value",
        "this-is-an-example": true,
        "some-optional-field": { (Optional)
            "more-fields": 12352356,
            ...
        }
    }

Attempt to do something mysterious to `<thing>` which must be a coffee
pot, and must not be in use by other users. If successful, the response
will include some cryptic information.

Response Body (on success):

    {
        "some-info": "Hello, World!",
        "numbers": [1,2,3]
    }

Authorization requirements:

* No special access.

Possible errors:

* 418, if `<thing>` is a teapot.
* 409, if:
  * `<thing>` does not exist
  * `<thing>` is busy


* `{"foo": <bar>, "baz": <quux>}` denotes a JSON object (in the body of
  the request).

# Core API Specification

API calls provided by the HaaS core. These are present in all
installations.

## Networks

### network_create

`PUT /network/<network>`

Request Body:

    {
        "creator": <creator>,
        "access": <access>,
        "net_id": <net_id>
    }

Create a network. For the semantics of each of the fields, see
[docs/networks.md](./networks.md).

Authorization requirements:

* If net_id is `''` and creator and access are the same project, then
  access to that project is required.
* Otherwise, administrative access is required.

Possible errors:

* 409, if a network by that name already exists.
* See also bug #461

### network_delete

`DELETE /network/<network>`

Delete a network. The user's project must be the creator of the network,
and the network must not be connected to any nodes or headnodes.
Finally, there may not be any pending actions involving the network.

Authorization requirements:

* If the creator is a project, access to that project is required.
* Otherwise, administrative access is required.

Possible Errors:

* 409 if:
    * The network is connected to a node or headnode.
    * There are pending actions involving the network.

### show_network

`GET /network/<network>`

View detailed information about `<network>`.

The result must contain the following fields:

* "name", the name of the network
* "channels", description of legal channel identifiers for this network.
  This is a list of channel identifiers, with possible wildcards. The
  format of these is driver specific, see below.
* "creator", the name of the project which created the network, or
  "admin", if it was created by an administrator.

The result may also contain the following fields:

* "access" -- if this is present, it is the name of the project which
  has access to the network. Otherwise, the network is public.

Response body (on success):

    {
        "name": <network>,
        "channels": <chanel-id-list>,
        "creator": <project or "admin">,
        "access": <project with access to the network> (Optional)
    }

Authorization requirements:

* If the network is public, no special access is required.
* Otherwise, access to the project specified by `"access"` is required.

#### Channel Formats

##### 802.1q VLAN based drivers

Channel identifiers for the VLAN based drivers are one of:

* `vlan/native`, to attach the network as the native (untagged) VLAN
* `vlan/<vlan_id>` where `<vlan_id>` is a VLAN id number. This attaches
   the network in tagged, mode, with the given VLAN id.

Additionally, the `show_networks` api call may return the channel identifier
`vlan/*`, which indicates that any VLAN-based channel id may be used.

Where documentation specifies that the network driver should choose a
default channel, the VLAN drivers choose `vlan/native`.

### node_connect_network

`POST /node/<node>/nic/<nic>/connect_network`

Request body:

    {
        "network": <network>,
        "channel": <channel> (Optional)
    }

Connect the network named `<network>` to `<nic>` on `<channel>`.

`<channel>` should be a legal channel identifier specified by the output
of `show_network`, above. If `<channel>` is omitted, the driver will choose
a default, which should be some form of "untagged."

Networks are connected and detached asynchronously. If successful, this
API call returns a status code of 202 Accepted, and queues the network
operation to be preformed. Each nic may have no more than one pending
network operation; an attempt to queue a second action will result in an
error.

Authorization requirements:

* Access to the project to which `<node>` is assigned.
* Either `<network>` must be public, or its `"access"` field must name
  the project to which `<node>` is assigned.

Possible errors:

* 409, if:
  * The current project does not control `<node>`.
  * The current project does not have access to `<network>`.
  * There is already a pending network operation on `<nic>`.
  * `<network>` is already attached to `<nic>` (possibly on a different channel).
  * The channel identifier is not legal for this network.

### node_detach_network

`POST /node/<node>/nic/<nic>/detach_network`

Request body:

    {
        "network": <network>
    }

Detach `<network>` from `<nic>`.

Networks are connected and detached asynchronously. If successful, this
API call returns a status code of 202 Accepted, and queues the network
operation to be preformed. Each nic may have no more than one pending
network operation; an attempt to queue a second action will result in an
error.

Authorization requirements:

* Access to the project to which `<node>` is assigned.

Possible Errors:

* 409, if:
  * The current project does not control `<node>`.
  * There is already a pending network operation on `<nic>`.
  * `<network>` is not attached to `<nic>`.

## Nodes

### node_register

Register a node with OBM of <type>

<type> (a string) is the type of OBM. The possible value depends on what drivers
HaaS is configured to use. The remainder of the field are driver-specific;
see the documentation of the OBM driver in question (read `docs/obm-drivers.md`).

`PUT /node/<node>`

Request Body:
        {"obm": { "type": <obm-subtype>,
                <additional sub-type specific values>}
        }

example provided in USING.rst

Register a node named `<node>` with the database.

Possible errors:

* 409, if a node with the name `<node>` already exists


### node_delete

`DELETE /node/<node>`

Delete the node named `<node>` from the database.

Authorization requirements:

* Administrative access.

### node_register_nic

`PUT /node/<node>/nic/<nic>`

Request Body:

    {
        "macaddr": <mac_addr>
    }

Register a nic named `<nic>` belonging to `<node>`. `<mac_addr>` should
be the nic's mac address. This isn't used by HaaS itself, but is useful
for users trying to configure their nodes.

Authorization requirements:

* Administrative access.

Possible errors:

* 409 if `<node>` already has a nic named `<nic>`

### node_delete_nic

`DELETE /node/<node>/nic/<nic>`

Delete the nic named `<nic>` and belonging to `<node>`.

Authorization requirements:

* Administrative access.

### node_power_cycle

`POST /node/<node>/power_cycle`

Power cycle the node named `<node>`, and set it's next boot device to
PXE. If the node is powered off, this turns it on.

### node_power_off

`POST /node/<node>/power_off`

Power off the node named `<node>`. If the node is already powered off,
this will have no effect.

Authorization requirements:

* Access to the project to which `<node>` is assigned (if any) or administrative access.

### list_free_nodes

`GET /free_nodes`

Return a list of free/available nodes.

Response body:

    [
        "node-1",
        "node-2",
        ...
    ]

Authorization requirements:

* No special access

### list_project_nodes

`GET /project/<project>/nodes`

List all nodes belonging to the given project

Response body:

    [
        "node-1",
        "node-2",
        ...
    ]

Authorization requirements:

* Access to `<project>` or administrative access

### show_node

`GET /node/<node>`

Show details of a node.

Returns a JSON object representing a node.
The object will have at least the following fields:

        * "name", the name/label of the node (string).
        * "project", the name of the project a node belongs to or null if the node does not belong to a project
        * "nics", a list of nics, each represted by a JSON object having
            at least the following fields:

                - "label", the nic's label.
                - "macaddr", the nic's mac address.
		- "networks", a JSON object describing what networks are attached to the nic. The keys are channels and the values are the names of networks attached to those channels.

Response body:

    {"name": "node1",
	 "project": "project1",
         "nics": [{"label": "nic1", "macaddr": "01:23:45:67:89", "networks": {"vlan/native": "pxe", "vlan/235": "storage"}},
                       {"label": "nic2", "macaddr": "12:34:56:78:90", "networks":{"vlan/native": "public"}}]
	}

Authorization requirements:

* If the node is free, no special access is required.
* Otherwise, access to the project to which `<node>` is assigned is
  required.

## Projects

### project_create

`PUT /project/<project>`

Create a project named `<project>`

Authorization requirements:

* Administrative access.

Possible Errors:

* 409, if the project already exists

### project_delete

`DELETE /project/<project>`

Delete the project named `<project>`

Authorization requirements:

* Administrative access.

Possible Errors:

* 409, if:
  * The project does not exist
  * The project still has resources allocated to it:
    * nodes
    * networks
    * headnodes

### project_connect_node

`POST /project/<project>/connect_node`

Request body:

    {
        "node": <node>
    }

Reserve the node named `<node>` for use by `<project>`. The node must be
free.

Authorization requirements:

* Access to `<project>` or administrative access.

Possible errors:

* 404, if the node or project does not exist.
* 409, if the node is not free.

### project_detach_node

`POST /project/<project>/detach_node`

    {
        "node": <node>
    }

Return `<node>` to the free pool. `<node>` must belong to the project
`<project>`. It must not be attached to any networks, or have any
pending network actions.

Authorization requirements:

* Access to `<project>` or administrative access.

* 409, if the node is attached to any networks, or has pending network
  actions.

### list_projects

`GET /projects`

Return a list of all projects in HaaS

Response body:

    [
        "manhattan",
        "runway",
        ...
    ]

Authorization requirements:

* Administrative access.

## Headnodes

### headnode_create

`PUT /headnode/<headnode>`

Request body:

    {
        "project": <project>,
        "base_img": <base_img>
    }

Create a headnode owned by project `<project>`, cloned from base image
`<base_img>`. `<base_img>` must be one of the installed base images.

Authorization requirements:

* Access to `<project>` or administrative access

Possible errors:

* 409, if a headnode named `<headnode>` already exists

### headnode_delete

`DELETE /headnode/<headnode>`

Delete the headnode named `<headnode>`.

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.

### headnode_start

`POST /headnode/<headnode>/start`

Start (power on) the headnode. Note that once a headnode has been
started, it cannot be modified (adding/removing hnics, changing
networks), only deleted --- even if it is stopped.

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.

### headnode_stop

`POST /headnode/<headnode>/stop`

Stop (power off) the headnode. This does a force power off; the VM is
not given the opportunity to shut down cleanly.

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.

### headnode_create_hnic

`PUT /headnode/<headnode>/hnic/<hnic>`

Create an hnic named `<hnic>` belonging to `<headnode>`. The headnode
must not have previously been started.

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.

Possible errors:

* 409, if:
  * The headnode already has an hnic by the given name.
  * The headnode has already been started.

### headnode_delete_hnic

`DELETE /headnode/<headnode>/hnic/<hnic>`

Delete the hnic named `<hnic>` and belonging to `<headnode>`. The
headnode must not have previously been started.

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.

Possible errors:

* 409, if the headnode has already been started.

### headnode_connect_network

`POST /headnode/<headnode>/hnic/<hnic>/connect_network`

Request body:

    {
        "network": <network>
    }

Connect the network named `<network>` to `<hnic>`.

`<network>` must be the name of a network which:

1. the headnode's project has the right to attach to, and
2. was not assigned a specific network id by an administrator (i.e. the
   network id was allocated dynamically by HaaS). This constraint is due
   to an implementation limitation, but will likely be lifted in the
   future; see issue #333.

Additionally, the headnode must not have previously been started.

Note that, unlike nodes, headnodes may only be attached via the
native/default channel (which is implicit, and may not be specified).

Rationale: separating headnodes from haas core is planned, and it has
been deemed not worth the development effort to adjust this prior to the
separation. Additionally, headnodes may have an arbitrary number of
nics, and so being able to attach two networks to the same nic is not as
important.

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.
* Either `<network>` must be public, or its `"access"` field must name
  the project which owns `<headnode>`.

Possible errors:

* 409, if the headnode has already been started.

### headnode_detach_network

`POST /headnode/<headnode>/hnic/<hnic>/detach_network`

Detach the network attached to `<hnic>`.  The headnode must not have
previously been started.

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.

Possible errors:

* 409, if the headnode has already been started.

### list_project_headnodes

`GET /project/<project>/headnodes`

Get a list of names of headnodes belonging to `<project>`.

Response body:

    [
        "<headnode1_name>",
        "<headnode2_name>",
        ...
    ]

Authorization requirements:

* Access to `<project>` or administrative access.

### show_headnode

`GET /headnode/<headnode>`

Get information about a headnode. Includes the following fields:

* "name", the name/label of the headnode (string).
* "project", the project to which the headnode belongs.
* "hnics", a JSON array of hnic names that are attached to this
    headnode.
* "vncport", the vnc port that the headnode VM is listening on; this
    value can be `null` if the VM is powered off or has not been
    created yet.

Response body:

    {
        "name": <headnode>,
        "project": <projectname>,
        "nics": [<nic1>, <nic2>, ...],
        "vncport": <port number>
    }

Authorization requirements:

* Access to the project which owns `<headnode>` or administrative access.

## Switches

### switch_register

Register a network switch of type `<type>`

`<type>` (a string) is the type of network switch. The possible values
depend on what drivers HaaS is configured to use. The remainder of the
fields are driver-specific; see the documentation for the driver in
question (in `docs/network-drivers.md`.

`PUT /switch/<switch>`

Request body:

    {
        "type": <type>,
        (extra args; depends on <type>)
    }

Authorization requirements:

* Administrative access.

Possible Errors:

* 409, if a switch named `<switch>` already exists.

### switch_delete

`DELETE /switch/<switch>`

Delete the switch named `<switch>`.

Prior to deleting a switch, all of the switch's ports must first be
deleted.

Authorization requirements:

* Administrative access.

Possible Errors:

* 409, if not all of the switch's ports have been deleted.

### switch_register_port

`PUT /switch/<switch>/port/<port>`

Register a port `<port>` on `<switch>`.

The permissible values of `<port>`, and their meanings, are switch
specific; see the documentation for the appropriate driver for more
information.

Authorization requirements:

* Administrative access.

Possible Errors:

* 409, if the port already exists

### switch_delete_port

`DELETE /switch/<switch>/port/<port>`

Delete the named `<port>` on `<switch>`.

Prior to deleting a port, any nic attached to it must be removed.

Authorization requirements:

* Administrative access.

Possible Errors:

* 409, if there is a nic attached to the port.

### port_connect_nic

`POST /switch/<switch>/port/<port>/connect_nic`

Request body:

    {
        "node": <node>,
        "nic": <nic>
    }

Connect a port a node's nic.

Authorization requirements:

* Administrative access.

Possible errors:

* 409, if the nic or port is already attached to something.

### port_detach_nic

`POST /switch/<switch>/port/<port>/detach_nic`

Detach the nic attached to `<port>`.

Authorization requirements:

* Administrative access.

Possible errors:

* 404, if the port is not attached to a nic
* 409, if the port is attached to a node which is not free.

# API Extensions

API calls provided by specific extensions. They may not exist in all
configurations.

## The `haas.ext.auth.database` auth backend

### user_create

`PUT /auth/basic/user/<username>`

Request body:

    {
        "password": <plaintext-password>
        "is-admin": <boolean> (Optional, defaults to False)
    }

Create a new user whose password is `<plaintext-password>`.

Authorization requirements:

* Administrative access.

Possible errors:

* 409, if the user already exists

### user_delete

`DELETE /auth/basic/user/<username>`

Delete the user whose username is `<username>`

Authorization requirements:

* Administrative access.

### user_add_project

`POST /auth/basic/user/<user>/add_project`

Request Body:

{
    "project": <project_name>
}

Add a user to a project.

Authorization requirements:

* Administrative access.

### user_remove_project

`POST /auth/basic/user/<user>/remove_project`

Request Body:

{
    "project": <project_name>
}

Remove a user from a project.

Authorization requirements:

* Administrative access.

